import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import Pango from 'gi://Pango';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const APP_ID = 'dev.bayhan.GnomeTodo';
const AGENDA_CACHE_TTL_USEC = 5 * GLib.USEC_PER_SEC;
const BACKGROUND_ERROR_TIMEOUT_MS = 3000;

const TodoPanelIndicator = GObject.registerClass(
class TodoPanelIndicator extends PanelMenu.Button {
    constructor(extension) {
        super(0.0, extension.gettext('Todo Panel'), false);
        this._extension = extension;
        this._menuOpen = false;
        this._queuedRefresh = false;
        this._submitting = false;
        this._agendaCache = {
            summary: null,
            fetchedAtMonotonic: 0,
            lastError: null,
            refreshInFlight: false,
        };

        const icon = new St.Icon({
            icon_name: 'checkbox-checked-symbolic',
            style_class: 'system-status-icon',
        });
        this.add_child(icon);

        this._entryItem = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false,
        });
        const entryBox = new St.BoxLayout({
            vertical: true,
            x_expand: true,
            style_class: 'todo-panel-entry-box',
        });
        this._entry = new St.Entry({
            hint_text: this._extension.gettext('Add a task…'),
            can_focus: true,
            x_expand: true,
            style_class: 'todo-panel-entry',
        });
        this._entry.clutter_text.connect('activate', () => {
            this._submitEntry();
        });
        entryBox.add_child(this._entry);
        this._entryItem.add_child(entryBox);
        this.menu.addMenuItem(this._entryItem);

        this._statusItem = new PopupMenu.PopupBaseMenuItem({
            reactive: false,
            can_focus: false,
        });
        this._statusItem.visible = false;
        this._statusLabel = new St.Label({
            style_class: 'todo-panel-status',
            x_expand: true,
        });
        this._statusItem.add_child(this._statusLabel);
        this.menu.addMenuItem(this._statusItem);

        this._agendaSection = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._agendaSection);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._openItem = this.menu.addAction(this._extension.gettext('Open Todo'), () => {
            this._launchApp();
        });

        this.menu.connect('open-state-changed', (_menu, open) => {
            this._menuOpen = open;
            if (!open)
                return;

            this._handleMenuOpened();
        });

        this._showLoading();
        this._ensureAgendaFresh({force: true});
    }

    destroy() {
        this._clearStatusTimeout();
        super.destroy();
    }

    _clearStatusTimeout() {
        if (this._statusTimeoutId) {
            GLib.source_remove(this._statusTimeoutId);
            this._statusTimeoutId = 0;
        }
    }

    _spawnFlatpak(args) {
        try {
            Gio.Subprocess.new(['flatpak', ...args], Gio.SubprocessFlags.NONE);
            return true;
        } catch (_error) {
            return false;
        }
    }

    _runFlatpakJson(args, callback) {
        let proc;
        try {
            proc = Gio.Subprocess.new(
                ['flatpak', ...args],
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE
            );
        } catch (error) {
            callback({ok: false, kind: 'missing-app', error});
            return;
        }

        proc.communicate_utf8_async(null, null, (subprocess, result) => {
            try {
                const [, stdout, stderr] = subprocess.communicate_utf8_finish(result);
                if (!subprocess.get_successful()) {
                    const message = (stderr || stdout || '').trim();
                    callback({
                        ok: false,
                        kind: this._isMissingAppMessage(message) ? 'missing-app' : 'error',
                        message,
                    });
                    return;
                }

                callback({
                    ok: true,
                    payload: JSON.parse(stdout),
                });
            } catch (error) {
                callback({ok: false, kind: 'error', error});
            }
        });
    }

    _isMissingAppMessage(message) {
        return message.includes(APP_ID) &&
            (message.includes('not installed') || message.includes('No such ref'));
    }

    _helperCommand(...args) {
        return ['run', `--command=todogui-panel`, APP_ID, ...args];
    }

    _handleMenuOpened() {
        if (this._agendaCache.summary)
            this._renderAgendaSummary(this._agendaCache.summary);
        else
            this._showLoading();

        this._ensureAgendaFresh();
    }

    _ensureAgendaFresh({force = false} = {}) {
        const hasCache = this._agendaCache.summary !== null;
        if (!force && hasCache && this._isAgendaCacheFresh())
            return;

        if (this._agendaCache.refreshInFlight) {
            if (force)
                this._queuedRefresh = true;
            return;
        }

        this._agendaCache.refreshInFlight = true;
        this._runFlatpakJson(this._helperCommand('summary', '--json'), result => {
            this._agendaCache.refreshInFlight = false;

            if (!result.ok) {
                this._handleAgendaRefreshError(result);
                this._runQueuedRefreshIfNeeded();
                return;
            }

            this._agendaCache.summary = result.payload;
            this._agendaCache.fetchedAtMonotonic = GLib.get_monotonic_time();
            this._agendaCache.lastError = null;
            if (this._menuOpen)
                this._renderAgendaSummary(result.payload);
            this._runQueuedRefreshIfNeeded();
        });
    }

    _createTaskItem(task) {
        const item = new PopupMenu.PopupBaseMenuItem({
            reactive: true,
            can_focus: true,
            style_class: 'todo-panel-task-item',
        });
        const box = new St.BoxLayout({
            vertical: true,
            x_expand: true,
        });

        const title = new St.Label({
            text: task.display_text || task.text,
            x_expand: true,
            style_class: 'todo-panel-task-title',
        });
        title.clutter_text.set_line_wrap(false);
        title.clutter_text.set_ellipsize(Pango.EllipsizeMode.END);
        box.add_child(title);

        const metaBox = new St.BoxLayout({
            style_class: 'todo-panel-meta-box',
        });
        let hasMeta = false;

        if (task.priority) {
            metaBox.add_child(this._makeBadge(task.priority, 'todo-panel-badge todo-panel-priority'));
            hasMeta = true;
        }
        if (task.due) {
            metaBox.add_child(this._makeBadge(`due ${task.due}`, 'todo-panel-badge'));
            hasMeta = true;
        }
        if (task.scheduled) {
            metaBox.add_child(this._makeBadge(
                `scheduled ${task.scheduled}`,
                'todo-panel-badge todo-panel-scheduled'
            ));
            hasMeta = true;
        }
        for (const [key, value] of Object.entries(task.keyvalues ?? {})) {
            if (!value || key === 'due' || key === 'scheduled')
                continue;

            metaBox.add_child(this._makeBadge(
                `${key} ${value}`,
                'todo-panel-badge todo-panel-keyvalue'
            ));
            hasMeta = true;
        }
        for (const context of task.contexts ?? []) {
            metaBox.add_child(this._makeBadge(`@${context}`, 'todo-panel-badge todo-panel-context'));
            hasMeta = true;
        }
        for (const project of task.projects ?? []) {
            metaBox.add_child(this._makeBadge(`+${project}`, 'todo-panel-badge todo-panel-project'));
            hasMeta = true;
        }

        if (hasMeta)
            box.add_child(metaBox);

        item.add_child(box);
        item.connect('activate', () => {
            this._launchApp();
        });
        return item;
    }

    _makeBadge(text, styleClass) {
        return new St.Label({
            text,
            style_class: styleClass,
            y_align: Clutter.ActorAlign.CENTER,
        });
    }

    _submitEntry() {
        const text = this._entry.get_text().trim();
        if (this._submitting || text.length === 0 || !this._entry.clutter_text.editable)
            return;

        this._submitting = true;
        this._setEntryEditable(false);
        this._setStatus(this._extension.gettext('Adding task…'), 'loading');

        this._runFlatpakJson(this._helperCommand('add', '--text', text, '--json'), result => {
            this._submitting = false;

            if (!result.ok) {
                this._setEntryEditable(true);
                const message = result.message || result.error?.message || this._extension.gettext('Could not add task.');
                this._setStatus(message, 'error');
                this._entry.grab_key_focus();
                return;
            }

            const payload = result.payload;
            if (!payload.ok) {
                this._setEntryEditable(payload.error !== 'Todo directory is not configured');
                this._setStatus(payload.error || _('Could not add task.'), 'error');
                if (this._entry.clutter_text.editable)
                    this._focusEntrySoon();
                return;
            }

            this._entry.set_text('');
            this._markAgendaCacheStale();
            this._ensureAgendaFresh({force: true});
        });
    }

    _launchApp() {
        this.menu.close();
        if (!this._spawnFlatpak(['run', APP_ID]))
            this._showMessage(this._extension.gettext('Todo Flatpak is not installed.'), 'missing-app');
    }

    _showLoading() {
        this._setEntryEditable(false);
        this._agendaSection.removeAll();
        this._setStatus(this._extension.gettext('Loading tasks…'), 'loading');
    }

    _showMessage(message, kind) {
        this._agendaSection.removeAll();
        this._setEntryEditable(kind !== 'missing-app' && kind !== 'missing-config');
        this._openItem.sensitive = kind !== 'missing-app';
        this._setStatus(message, kind);
    }

    _setEntryEditable(editable) {
        this._entry.clutter_text.set_editable(editable);
        this._entry.reactive = editable;
        this._entry.can_focus = editable;
    }

    _focusEntrySoon() {
        if (!this._menuOpen)
            return;

        GLib.idle_add(GLib.PRIORITY_DEFAULT, () => {
            this._entry.grab_key_focus();
            return GLib.SOURCE_REMOVE;
        });
    }

    _renderAgendaSummary(summary) {
        this._currentSummary = summary;

        if (!summary.configured) {
            this._showMessage(
                this._extension.gettext('Choose your todo.txt folder in the Todo app first.'),
                'missing-config'
            );
            return;
        }

        this._setEntryEditable(true);
        this._openItem.sensitive = true;
        this._agendaSection.removeAll();
        this._setStatus('', '');

        if (summary.counts.total === 0) {
            this._showMessage(
                this._extension.gettext('No overdue, due-today, or scheduled-today tasks.'),
                'empty'
            );
            this._focusEntrySoon();
            return;
        }

        this._statusItem.visible = false;
        for (const sectionName of ['overdue', 'due_today', 'scheduled_today']) {
            const items = summary.sections[sectionName];
            if (!items || items.length === 0)
                continue;

            this._agendaSection.addMenuItem(
                new PopupMenu.PopupSeparatorMenuItem(
                    `${this._sectionTitle(sectionName)} (${items.length})`
                )
            );
            for (const task of items)
                this._agendaSection.addMenuItem(this._createTaskItem(task));
        }
        this._focusEntrySoon();
    }

    _handleAgendaRefreshError(result) {
        const hasCache = this._agendaCache.summary !== null;
        const message = result.kind === 'missing-app'
            ? this._extension.gettext('Todo Flatpak is not installed.')
            : result.message || result.error?.message || this._extension.gettext('Could not load tasks.');

        this._agendaCache.lastError = {
            kind: result.kind,
            message,
        };

        if (hasCache) {
            if (this._menuOpen)
                this._setStatus(message, 'error', BACKGROUND_ERROR_TIMEOUT_MS);
            return;
        }

        if (!this._menuOpen)
            return;

        if (result.kind === 'missing-app') {
            this._showMessage(message, 'missing-app');
            return;
        }

        this._showMessage(message, 'error');
    }

    _isAgendaCacheFresh() {
        if (!this._agendaCache.summary)
            return false;

        return GLib.get_monotonic_time() - this._agendaCache.fetchedAtMonotonic < AGENDA_CACHE_TTL_USEC;
    }

    _markAgendaCacheStale() {
        this._agendaCache.fetchedAtMonotonic = 0;
    }

    _runQueuedRefreshIfNeeded() {
        if (!this._queuedRefresh)
            return;

        this._queuedRefresh = false;
        this._ensureAgendaFresh({force: true});
    }

    _sectionTitle(sectionName) {
        const titles = {
            overdue: this._extension.gettext('Overdue'),
            due_today: this._extension.gettext('Due Today'),
            scheduled_today: this._extension.gettext('Scheduled Today'),
        };
        return titles[sectionName] ?? sectionName;
    }

    _setStatus(message, kind, timeoutMs = 0) {
        this._clearStatusTimeout();

        if (!message) {
            this._statusItem.visible = false;
            this._statusLabel.text = '';
            this._statusLabel.style_class = 'todo-panel-status';
            return;
        }

        this._statusItem.visible = true;
        this._statusLabel.text = message;
        this._statusLabel.style_class = `todo-panel-status ${kind}`;

        if (timeoutMs > 0) {
            this._statusTimeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, timeoutMs, () => {
                this._statusTimeoutId = 0;
                this._setStatus('', '');
                return GLib.SOURCE_REMOVE;
            });
        }
    }
});

export default class TodoPanelExtension extends Extension {
    enable() {
        this._indicator = new TodoPanelIndicator(this);
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
