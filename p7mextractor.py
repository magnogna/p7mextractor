#!/usr/bin/env python3
import os
import subprocess
import threading
import logging
import sys
import shutil
import gettext
import locale
import gi

# --- GTK 4 & LIBADWAITA CHECK ---
try:
    gi.require_version('Gtk', '4.0')
    gi.require_version('Adw', '1')
    from gi.repository import Gtk, GLib, Gio, GObject, Gdk, Adw
except ValueError:
    print("Error: GTK 4 or Libadwaita is not installed.")
    sys.exit(1)

# --- CONSTANTS ---
APP_NAME = "p7mextractor"
DATA_DIR = os.path.join(GLib.get_user_data_dir(), APP_NAME)
LOG_FILE = os.path.join(DATA_DIR, "app.log")

os.makedirs(DATA_DIR, exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- INTERNATIONALIZATION ---
SYSTEM_LOCALE_PATH = "/app/share/locale"
LOCAL_LOCALE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "locales")
LOCALE_DIR = SYSTEM_LOCALE_PATH if os.path.exists(SYSTEM_LOCALE_PATH) else LOCAL_LOCALE_PATH

try:
    # Force C locale to parse env vars correctly
    locale.setlocale(locale.LC_ALL, '')
    
    # Robust Language Detection for Flatpak
    lang_code = os.environ.get('LC_ALL') or os.environ.get('LC_MESSAGES') or os.environ.get('LANG')
    if lang_code:
        lang_code = lang_code.split('.')[0]
        languages = [lang_code, lang_code.split('_')[0], 'en']
    else:
        languages = ['en']

    lang = gettext.translation(APP_NAME, localedir=LOCALE_DIR, languages=languages, fallback=True)
    lang.install()
except Exception as e:
    logging.warning(f"Translation setup failed: {e}")
    def _(s): return s

# --- DATA MODEL ---
class FileItem(GObject.Object):
    __gtype_name__ = 'FileItem'
    id = GObject.Property(type=str)
    filename = GObject.Property(type=str)
    path = GObject.Property(type=str)
    status = GObject.Property(type=str)
    full_path = GObject.Property(type=str)

    def __init__(self, id, filename, path, full_path, status):
        super().__init__()
        self.id = id
        self.filename = filename
        self.path = path
        self.full_path = full_path
        self.status = status

class P7MExtractorApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.p7mextractor", flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.file_queue = []
        self.custom_export_path = None

    def do_activate(self):
        win = Adw.ApplicationWindow(application=self, title=_("P7M Extractor"))
        win.set_default_size(800, 600)

        # --- ACTIONS ---
        action_files = Gio.SimpleAction.new("add-files", None)
        action_files.connect("activate", self.on_add_files_action)
        win.add_action(action_files)

        action_folder = Gio.SimpleAction.new("add-folder", None)
        action_folder.connect("activate", self.on_add_folder_action)
        win.add_action(action_folder)

        # --- CSS ---
        # @accent_color is provided automatically by Adw.Application
        css = b"""
        .drag-active {
            background-color: alpha(@accent_color, 0.1);
            border: 4px dashed @accent_color;
            border-radius: 12px;
            transition: all 0.2s ease;
        }
        """
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # --- LAYOUT ---
        toolbar_view = Adw.ToolbarView()
        win.set_content(toolbar_view)

        # Header
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Content Box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        toolbar_view.set_content(self.main_box)

        # Menu Button
        menu = Gio.Menu()
        menu.append(_("Add Files..."), "win.add-files")
        menu.append(_("Add Folder..."), "win.add-folder")

        self.btn_add_menu = Gtk.MenuButton()
        self.btn_add_menu.set_icon_name("list-add-symbolic")
        self.btn_add_menu.set_tooltip_text(_("Add Files or Folders"))
        self.btn_add_menu.set_menu_model(menu)
        header.pack_start(self.btn_add_menu)

        btn_clear = Gtk.Button(icon_name="edit-clear-symbolic")
        btn_clear.set_tooltip_text(_("Clear List"))
        btn_clear.connect("clicked", self.on_clear_clicked)
        header.pack_start(btn_clear)

        self.btn_convert = Gtk.Button(label=_("Extract"))
        self.btn_convert.add_css_class("suggested-action")
        self.btn_convert.set_sensitive(False)
        self.btn_convert.connect("clicked", self.on_convert_clicked)
        header.pack_end(self.btn_convert)

        # Progress Bar
        self.progress_bar = Gtk.ProgressBar()
        self.main_box.append(self.progress_bar)

        # List View Setup
        self.model = Gio.ListStore(item_type=FileItem)
        self.column_view = Gtk.ColumnView(model=Gtk.SingleSelection(model=self.model))
        
        self._create_column("#", self._on_bind_id)
        col_name = self._create_column(_("File Name"), self._on_bind_filename)
        col_name.set_expand(True)
        self._create_column(_("Path"), self._on_bind_path)
        self._create_column(_("Status"), self._on_bind_status)

        # Scroll Wrapper (Drop Zone)
        self.scroll_wrapper = Gtk.ScrolledWindow()
        self.scroll_wrapper.set_child(self.column_view)
        self.scroll_wrapper.set_vexpand(True)
        for margin in ["top", "bottom", "start", "end"]:
            getattr(self.scroll_wrapper, f"set_margin_{margin}")(8)
            
        self.main_box.append(self.scroll_wrapper)

        # Destination Config
        dest_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        dest_box.set_margin_top(10)
        dest_box.set_margin_bottom(10)
        dest_box.set_margin_start(10)
        dest_box.set_margin_end(10)
        dest_box.add_css_class("card")
        
        self.switch_dest = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.switch_dest.connect("notify::active", self.on_dest_switch_toggled)
        dest_box.append(self.switch_dest)
        dest_box.append(Gtk.Label(label=_("Save to specific folder")))

        self.lbl_dest_path = Gtk.Label(label=_("Same as source file"), ellipsize=3, hexpand=True, xalign=1.0, sensitive=False)
        dest_box.append(self.lbl_dest_path)

        self.btn_pick = Gtk.Button(icon_name="document-open-symbolic", tooltip_text=_("Choose Folder"), sensitive=False)
        self.btn_pick.connect("clicked", self.on_pick_dest_clicked)
        dest_box.append(self.btn_pick)
        self.main_box.append(dest_box)

        # Status Bar
        action_bar = Gtk.ActionBar()
        self.lbl_count = Gtk.Label(label=_("No files added"))
        self.lbl_status = Gtk.Label(label=_("Ready"))
        action_bar.pack_start(self.lbl_count)
        action_bar.pack_end(self.lbl_status)
        self.main_box.append(action_bar)

        # Drag & Drop Controller
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("enter", self.on_drag_enter)
        drop_target.connect("leave", self.on_drag_leave)
        drop_target.connect("drop", self.on_drop)
        self.scroll_wrapper.add_controller(drop_target)

        win.present()
        self.check_openssl()

    # --- UI HELPERS ---
    def _create_column(self, title, bind_func):
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", lambda f, i: i.set_child(Gtk.Label(xalign=0.0)))
        factory.connect("bind", bind_func)
        col = Gtk.ColumnViewColumn(title=title, factory=factory)
        self.column_view.append_column(col)
        return col

    def _on_bind_id(self, factory, item): item.get_child().set_text(item.get_item().id)
    def _on_bind_filename(self, factory, item): item.get_child().set_text(item.get_item().filename)
    def _on_bind_path(self, factory, item): item.get_child().set_text(item.get_item().path)
    def _on_bind_status(self, factory, item): 
        item.get_item().bind_property("status", item.get_child(), "label", GObject.BindingFlags.SYNC_CREATE)

    # --- ACTION HANDLERS ---
    def on_add_files_action(self, action, param):
        self._open_file_dialog(_("Add Files"), self.on_open_multiple_finish, multiple=True)

    def on_add_folder_action(self, action, param):
        self._open_file_dialog(_("Select Folder"), self.on_select_input_folder_finish, folder=True)

    def _open_file_dialog(self, title, callback, multiple=False, folder=False):
        dialog = Gtk.FileDialog(title=title)
        if not folder:
            filters = Gio.ListStore(item_type=Gtk.FileFilter)
            f = Gtk.FileFilter(name="P7M Files")
            f.add_pattern("*.p7m")
            f.add_pattern("*.P7M")
            filters.append(f)
            dialog.set_filters(filters)
            dialog.set_default_filter(f)
            
        if folder:
            dialog.select_folder(self.btn_add_menu.get_root(), None, callback, None)
        else:
            dialog.open_multiple(self.btn_add_menu.get_root(), None, callback, None)

    def on_open_multiple_finish(self, dialog, result, data):
        try:
            file_list = dialog.open_multiple_finish(result)
            for i in range(file_list.get_n_items()):
                self.add_file_to_queue(file_list.get_item(i).get_path())
        except GLib.Error: pass

    def on_select_input_folder_finish(self, dialog, result, data):
        try:
            gfile = dialog.select_folder_finish(result)
            self.process_added_items([gfile.get_path()])
        except GLib.Error: pass

    # --- CORE LOGIC ---
    def process_added_items(self, paths):
        added = 0
        for path in paths:
            if os.path.isfile(path) and path.lower().endswith('.p7m'):
                self.add_file_to_queue(path)
                added += 1
            elif os.path.isdir(path):
                # Using 'dirs' instead of '_' to protect translation function
                for root, dirs, filenames in os.walk(path):
                    for name in filenames:
                        if name.lower().endswith('.p7m'):
                            self.add_file_to_queue(os.path.join(root, name))
                            added += 1
        if added > 0: self.lbl_status.set_label(f"{_('Added')} {added} {_('files')}")

    def on_drop(self, target, file_list, x, y):
        self.scroll_wrapper.remove_css_class("drag-active")
        self.process_added_items([f.get_path() for f in file_list.get_files()])
        return True

    def on_drag_enter(self, target, x, y):
        self.scroll_wrapper.add_css_class("drag-active")
        return Gdk.DragAction.COPY

    def on_drag_leave(self, target):
        self.scroll_wrapper.remove_css_class("drag-active")

    def add_file_to_queue(self, path):
        if path in self.file_queue: return
        self.file_queue.append(path)
        item = FileItem(str(len(self.file_queue)), os.path.basename(path), os.path.dirname(path), path, _("Pending"))
        self.model.append(item)
        self.update_ui_state()

    def on_clear_clicked(self, btn):
        self.file_queue.clear()
        self.model.remove_all()
        self.update_ui_state()

    def update_ui_state(self):
        count = self.model.get_n_items()
        self.lbl_count.set_label(f"{count} {_('files ready')}")
        self.btn_convert.set_sensitive(count > 0)

    # --- DESTINATION & CONVERSION ---
    def on_dest_switch_toggled(self, switch, param):
        active = switch.get_active()
        self.btn_pick.set_sensitive(active)
        self.lbl_dest_path.set_sensitive(active)
        if not active:
            self.custom_export_path = None
            self.lbl_dest_path.set_label(_("Same as source file"))
        elif not self.custom_export_path:
            self.on_pick_dest_clicked(self.btn_pick)

    def on_pick_dest_clicked(self, btn):
        dialog = Gtk.FileDialog(title=_("Select Export Folder"))
        dialog.select_folder(btn.get_root(), None, self.on_select_folder_finish, None)

    def on_select_folder_finish(self, dialog, result, data):
        try:
            gfile = dialog.select_folder_finish(result)
            self.custom_export_path = gfile.get_path()
            self.lbl_dest_path.set_label(self.custom_export_path)
            self.switch_dest.set_active(True)
        except GLib.Error:
            if not self.custom_export_path: self.switch_dest.set_active(False)

    def check_openssl(self):
        if not shutil.which("openssl"):
            self.lbl_status.set_label(_("Error: OpenSSL not found"))
            self.btn_convert.set_sensitive(False)

    def on_convert_clicked(self, btn):
        self.btn_convert.set_sensitive(False)
        self.progress_bar.set_fraction(0.0)
        threading.Thread(target=self.run_conversion_thread, daemon=True).start()

    def run_conversion_thread(self):
        openssl = shutil.which("openssl")
        count = self.model.get_n_items()
        
        for i in range(count):
            item = self.model.get_item(i)
            GLib.idle_add(lambda: item.set_property("status", _("Processing...")))
            
            base = os.path.splitext(item.filename)[0] + ".pdf"
            dest = self.custom_export_path if self.custom_export_path else item.path
            out_path = os.path.join(dest, base)
            
            cmd = [openssl, "smime", "-verify", "-noverify", "-binary", "-inform", "DER", "-in", item.full_path, "-out", out_path]
            
            try:
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                success = (res.returncode == 0)
            except Exception as e:
                logging.error(f"Conversion error: {e}")
                success = False

            status = _("Done") if success else _("Error")
            GLib.idle_add(lambda s=status: item.set_property("status", s))
            GLib.idle_add(self.progress_bar.set_fraction, (i + 1) / count)

        GLib.idle_add(self.finish_conversion)

    def finish_conversion(self):
        self.lbl_status.set_label(_("Extraction Complete"))
        self.btn_convert.set_sensitive(True)

if __name__ == "__main__":
    app = P7MExtractorApp()
    app.run(sys.argv)
