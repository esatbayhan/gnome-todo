project(
  'todogui',
  version: '0.3.0',
  meson_version: '>= 0.59.0',
  default_options: ['warning_level=2'],
)

python = import('python')
gnome = import('gnome')

application_id = 'dev.bayhan.GnomeTodo'
pkgdatadir = join_paths(get_option('prefix'), get_option('datadir'), meson.project_name())

py_installation = python.find_installation('python3')

dependency('gtk4')
dependency('libadwaita-1', version: '>= 1.4')

subdir('data')
subdir('src')

gnome.post_install(
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
