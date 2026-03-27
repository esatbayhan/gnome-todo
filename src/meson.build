pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())
moduledir = join_paths(pkgdatadir, 'todotxt_gui')
libdir = join_paths(pkgdatadir, 'todotxt_lib')
devtoolsdir = join_paths(pkgdatadir, 'todotxt_gui_devtools')
fs = import('fs')

# Blueprint compilation
blueprints = custom_target('blueprints',
  input: files(
    'ui/window.blp',
    'ui/add_task_dialog.blp',
    'ui/welcome_dialog.blp',
    'ui/preferences_dialog.blp',
    'ui/content_header.blp',
    'ui/task_row.blp',
    'ui/task_detail_panel.blp',
    'ui/smart_filter_row.blp',
  ),
  output: '.',
  command: [
    find_program('blueprint-compiler'),
    'batch-compile',
    '@OUTPUT@',
    '@CURRENT_SOURCE_DIR@',
    '@INPUT@',
  ],
)

# GResource bundle
gnome.compile_resources('todogui',
  'dev.bayhan.GnomeTodo.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  dependencies: blueprints,
)

# Launcher script
conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'todogui.in',
  output: 'todogui',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

configure_file(
  input: 'todogui-panel.in',
  output: 'todogui-panel',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x',
)

# Install todotxt_gui Python package
gui_sources = [
  'todotxt_gui/__init__.py',
  'todotxt_gui/app.py',
  'todotxt_gui/_config.py',
  'todotxt_gui/_content.py',
  'todotxt_gui/_content_header.py',
  'todotxt_gui/_core.py',
  'todotxt_gui/_detail_panel.py',
  'todotxt_gui/_detail_panel_tags.py',
  'todotxt_gui/_dialogs.py',
  'todotxt_gui/_file_monitor.py',
  'todotxt_gui/_preferences.py',
  'todotxt_gui/_shortcuts.py',
  'todotxt_gui/_sidebar.py',
  'todotxt_gui/_sidebar_state.py',
  'todotxt_gui/_task_row_state.py',
  'todotxt_gui/_ui.py',
  'todotxt_gui/_task_row.py',
  'todotxt_gui/_welcome.py',
  'todotxt_gui/_widgets.py',
  'todotxt_gui/_window.py',
  'todotxt_gui/_window_state.py',
  'todotxt_gui/panel_cli.py',
]
install_data(gui_sources, install_dir: moduledir)

if fs.is_dir(join_paths(meson.current_source_dir(), 'todotxt_gui_devtools'))
  devtools_sources = [
    'todotxt_gui_devtools/__init__.py',
    'todotxt_gui_devtools/screenshot.py',
  ]
  install_data(devtools_sources, install_dir: devtoolsdir)
endif

# Install todotxt_lib Python package
lib_sources = [
  'todotxt_lib/__init__.py',
  'todotxt_lib/env.py',
  'todotxt_lib/filtering.py',
  'todotxt_lib/grouping.py',
  'todotxt_lib/mutations.py',
  'todotxt_lib/operations.py',
  'todotxt_lib/parser.py',
  'todotxt_lib/task.py',
  'todotxt_lib/text_editing.py',
  'todotxt_lib/todo_directory.py',
  'todotxt_lib/todo_file.py',
]
install_data(lib_sources, install_dir: libdir)
