# NVDA Add-on: Speech History
# Copyright (C) 2012 Tyler Spivey
# Copyright (C) 2015-2025 James Scholes
# This add-on is free software, licensed under the terms of the GNU General Public License (version 2).
# See the file LICENSE for more details.

from collections import deque
import addonHandler
import api
import config
import globalPluginHandler
import speech
import speechViewer
import tones
import ui
import versionInfo
from queueHandler import queueFunction, eventQueue
from eventHandler import FocusLossCancellableSpeechCommand
from gui.settingsDialogs import NVDASettingsDialog
from scriptHandler import script, getLastScriptRepeatCount
from functools import wraps
from .settings import SpeechHistorySettingsPanel
from .constants import (CONFIG_SECTION, POST_COPY_BEEP, POST_COPY_SPEAK, POST_COPY_BOTH, MAX_SPELL_LENGTH, HTML_CONTAINER_START, HTML_CONTAINER_END, HTML_ITEM_START, HTML_ITEM_END, confspec, COMMAND_LAYER_GESTURES)

try:
	import nh3
	HTML_FORMAT_HISTORY_SUPPORTED = True
except ImportError:
	HTML_FORMAT_HISTORY_SUPPORTED = False


addonHandler.initTranslation()

BUILD_YEAR = getattr(versionInfo, 'version_year', 2021)
SCRIPT_CATEGORY = _('Speech History')

def makeHTMLList(strings):
	if HTML_FORMAT_HISTORY_SUPPORTED:
		listItems = '\n'.join((f'{HTML_ITEM_START}{string}{HTML_ITEM_END}' for string in map(nh3.clean_text, strings)))
		return f'{HTML_CONTAINER_START}\n{listItems}\n{HTML_CONTAINER_END}'
	else:
		return '\n'.join(strings)

def finally_(func, final):
	@wraps(func)
	def wrapper(*args, **kwargs):
		try:
			return func(*args, **kwargs)
		finally:
			final()
	return wrapper


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		config.conf.spec[CONFIG_SECTION] = confspec
		if SpeechHistorySettingsPanel not in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.append(SpeechHistorySettingsPanel)

		self._history = deque(maxlen=config.conf[CONFIG_SECTION]['maxHistoryLength'])
		self.history_pos = 0
		self._recorded = []
		self._recording = False
		self._record = False
		self.ignore_history = False
		self.layer = False
		self._patch()

	def _patch(self):
		if BUILD_YEAR >= 2021:
			self.oldSpeak = speech.speech.speak
			speech.speech.speak = self.mySpeak
		else:
			self.oldSpeak = speech.speak
			speech.speak = self.mySpeak

	# Translators: Documentation string for copy currently selected speech history item script
	@script(description=_('Copy the currently selected speech history item to the clipboard, which by default will be the most recently spoken text by NVDA.'), category=SCRIPT_CATEGORY)
	def script_copyLast(self, gesture):
		if not self._history:
			self.oldSpeak([_("No history items")])
			tones.beep(200, 100)
			return
		self.copyHistoryItemText(self._history[self.history_pos])

	# Translators: Documentation string for previous speech history item script
	@script(description=_('Review the previous item in NVDA\'s speech history.'), category=SCRIPT_CATEGORY)
	def script_prevString(self, gesture):
		if not self._history:
			self.oldSpeak([_("No history items")])
			tones.beep(200, 100)
			return
		self.history_pos += 1
		if self.history_pos > len(self._history) - 1:
			tones.beep(200, 100)
			self.history_pos -= 1
		self.oldSpeak(self._history[self.history_pos])

	# Translators: Documentation string for next speech history item script
	@script(description=_('Review the next item in NVDA\'s speech history.'), category=SCRIPT_CATEGORY)
	def script_nextString(self, gesture):
		if not self._history:
			self.oldSpeak([_("No history items")])
			tones.beep(200, 100)
			return
		self.history_pos -= 1
		if self.history_pos < 0:
			tones.beep(200, 100)
			self.history_pos += 1

		self.oldSpeak(self._history[self.history_pos])

	# Translators: Documentation string for start recording script
	@script(description=_('Start recording NVDA\'s speech output, for copying multiple announcements to the clipboard.'), category=SCRIPT_CATEGORY)
	def script_startRecording(self, gesture):
		if self._recording or self._record:
			# Translators: Message spoken when speech recording is already active
			tones.beep(200, 100)
			self.oldSpeak([_('Already recording speech')])
			return

		self._recording = True
		self._record = True
		if config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record']:
			tones.beep(1500, 80)
		# Translators: Message spoken when speech recording is started
		self.oldSpeak([_('Started recording speech')])

	# Translators: Documentation string for stop recording script
	@script(description=_('Stop recording NVDA\'s speech output, and copy the recorded announcements to the clipboard.'), category=SCRIPT_CATEGORY)
	def script_stopRecording(self, gesture):
		if not self._recording:
			# Translators: Message spoken when speech recording is not already active
			tones.beep(200, 100)
			self.oldSpeak([_('Not currently recording speech')])
			return

		self._recording = False
		self._record = False
		if config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record']:
			tones.beep(800, 80)
		# Translators: Message spoken when speech recording is stopped
		self.oldSpeak([_('Recorded speech copied to clipboard')])
		api.copyToClip('\n'.join(self._recorded))
		self._recorded.clear()

	# Translators: Documentation string for pause recording script
	@script(description=_('Pause recording NVDA\'s speech output, and copy the recorded announcements to the clipboard.'), category=SCRIPT_CATEGORY)
	def script_pauseRecording(self, gesture):
		if not self._record:
			# Translators: Message spoken when not recording speech
			self.oldSpeak([_('Not currently recording speech')])
			tones.beep(200, 100)
			return

		if self._recording:
			self._recording = False
			if config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record']:
				tones.beep(800, 80)

			# Translators: Message spoken when speech recording is paused
			self.oldSpeak([_('Paursed recording speech')])
		else:
			self._recording = True
			if config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record']:
				tones.beep(1500, 80)

			# Translators: Message spoken when speech recording is restarted
			self.oldSpeak([_('Recording speech restarted')])

	# Translators: Documentation string for show speech history script
	@script(description=_("Show NVDA's speech history in a browseable list."), category=SCRIPT_CATEGORY)
	def script_showHistory(self, gesture):
		if not self._history:
			# Translators: A message shown when users try to view their speech history but it's empty.
			self.oldSpeak([_('No history items.')])
			tones.beep(200, 100)
			return

		if not HTML_FORMAT_HISTORY_SUPPORTED:
			# Translators: A message shown when HTML formatting is unavailable for speech history.
			self.oldSpeak([_('Warning: HTML formatting is unavailable. Showing speech history as plain text.')])

		message = makeHTMLList((self.getSequenceText(item) for item in self._history))

		# Translators: The title of the speech history window.
		title = _('Speech History')

		try:
			# HTML history items are already sanitized above.
			ui.browseableMessage(message=message, title=title, isHtml=HTML_FORMAT_HISTORY_SUPPORTED, copyButton=True, closeButton=True, sanitizeHtmlFunc=lambda string: string)
		except TypeError:
			ui.browseableMessage(message=message, title=title, isHtml=HTML_FORMAT_HISTORY_SUPPORTED, closeButton=True)

	# Translators: Documentation string for copy all speech history script
	@script(description=_("Copy all NVDA's speech history to clipboard."), category=SCRIPT_CATEGORY)
	def script_copyAllHistory(self, gesture):
		if not self._history:
			self.oldSpeak([_("No history items")])
			tones.beep(200, 100)
			return
		sentences = []
		for seq in self._history:
			text = self.getTrimmedSequenceText(seq)
			sentences.append(text)

		postCopyAction = config.conf[CONFIG_SECTION]['postCopyAction']
		if api.copyToClip("\n".join(sentences)):
			if postCopyAction in (POST_COPY_BEEP, POST_COPY_BOTH):
				tones.beep(config.conf[CONFIG_SECTION]['beepFrequency'], config.conf[CONFIG_SECTION]['beepDuration'])
			if postCopyAction in (POST_COPY_SPEAK, POST_COPY_BOTH):
				# Translators: A short confirmation message spoken after copying a speech history item.
				self.oldSpeak([_('All history copied')])

	# Translators: Documentation string for clear all speech history script
	@script(description=_("Clear all NVDA's speech history."), category=SCRIPT_CATEGORY)
	def script_clearHistory(self, gesture):
		if not self._history:
			self.oldSpeak([_("No history items")])
			tones.beep(200, 100)
			return
		self._history.clear()
		self.history_pos = 0
		self.oldSpeak([_('History cleared')])

	# Translators: Documentation string for Repeat what NVDA just said script
	@script(description=_("Press once to repeat what NVDA just said, double to spell and triple to show in a browseable dialog."), category=SCRIPT_CATEGORY)
	def script_repeatMostRecentSpeech(self, gesture):
		if not self._history:
			self.oldSpeak([_("No history items")])
			tones.beep(200, 100)
			return

		repeat = getLastScriptRepeatCount()
		if repeat == 1:
			text = self.getTrimmedSequenceText(self._history[0])
			if not text:
				self.oldSpeak([_("No text to spell")])
				return
			if len(text) > MAX_SPELL_LENGTH:
				self.oldSpeak([_('The text is too long. It contains {} characters.').format(len(text))])
				return
			self.ignore_history = True
			try:
				speech.speakSpelling(text)
			finally:
				self.ignore_history = False
		elif repeat == 2:
			ui.browseableMessage(message=self.getTrimmedSequenceText(self._history[0]), copyButton=True, closeButton=True)
		else:
			self.oldSpeak(self._history[0])

	# Translators: Documentation string for copy  most recently NVDA's speech to clipboard script
	@script(description=_("Copy most recently NVDA's speech to clipboard."), category=SCRIPT_CATEGORY)
	def script_copyMostRecentSpeech(self, gesture):
		if not self._history:
			self.oldSpeak([_("No history items")])
			tones.beep(200, 100)
			return

		self.copyHistoryItemText(self._history[0])

	# Translators: Documentation string for    move to beginning of speech history item script
	@script(description=_('Review the beginning item in NVDA\'s speech history.'), category=SCRIPT_CATEGORY)
	def script_beginningString(self, gesture):
		if not self._history:
			self.oldSpeak([_("No history items")])
			tones.beep(200, 100)
			return

		self.history_pos = 0
		self.oldSpeak(self._history[self.history_pos])
		tones.beep(200, 100)

	# Translators: Documentation string for move to last speech history item script
	@script(description=_('Review the last item in NVDA\'s speech history.'), category=SCRIPT_CATEGORY)
	def script_lastString(self, gesture):
		if not self._history:
			self.oldSpeak([_("No history items")])
			tones.beep(200, 100)
			return

		self.history_pos = len(self._history) - 1
		self.oldSpeak(self._history[self.history_pos])
		tones.beep(200, 100)

	# Translators: Document string for Speech History command layer help script
	@script(description=_('Speech History command layer help.'), category=SCRIPT_CATEGORY)
	def script_speechHistoryCommandLayerHelp(self, gesture):
		lines = []

		for gestureName, scriptName in COMMAND_LAYER_GESTURES.items():
			script = getattr(self, "script_" + scriptName, None)

			if script:
				description = script.__doc__ or _("No description")
			lines.append(f"{gestureName[3:].title()}: {description}")
		lines.append(_('Escape: Exit command layer.'))

		message = "\n".join(lines)

		ui.browseableMessage(message=message, title=_("Speech History command layer help"), copyButton=True, closeButton=True)

	# Translators: Document string for Speech History command layer script
	@script(description=_('Activate Speech History command layer.'), category=SCRIPT_CATEGORY)
	def script_SpeechHistoryCommandLayer(self, gesture):
		if self.layer:
			tones.beep(200, 100)
			return

		self.layer = True
		self.bindGestures(COMMAND_LAYER_GESTURES)
		tones.beep(400, 100)

	def script_commandLayerError(self, gesture):
		tones.beep(200, 100)

	def finish(self):
		self.layer = False
		self.clearGestureBindings()
		self.bindGestures(self.__gestures)

	def terminate(self, *args, **kwargs):
		if BUILD_YEAR >= 2021:
			speech.speech.speak = self.oldSpeak
		else:
			speech.speak = self.oldSpeak
		if SpeechHistorySettingsPanel in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.remove(SpeechHistorySettingsPanel)
		super().terminate(*args, **kwargs)

	def getScript(self, gesture):
		if not self.layer:
			return super().getScript(gesture)

		script = super().getScript(gesture)

		if not script:
			return finally_(self.script_commandLayerError, self.finish)

		if script.__name__ in ("script_prevString", "script_nextString", "script_beginningString", "script_lastString"):
			return script

		return finally_(script, self.finish)

	def append_to_history(self, seq):
		seq = [command for command in seq if not isinstance(command, FocusLossCancellableSpeechCommand)]
		self._history.appendleft(seq)
		self.history_pos = 0
		if self._recording:
			self._recorded.append(self.getSequenceText(seq))

	def mySpeak(self, sequence, *args, **kwargs):
		self.oldSpeak(sequence, *args, **kwargs)
		if not self.ignore_history:
			text = self.getSequenceText(sequence)
			if text.strip():
				queueFunction(eventQueue, self.append_to_history, sequence)

	def getSequenceText(self, sequence):
		return speechViewer.SPEECH_ITEM_SEPARATOR.join([x for x in sequence if isinstance(x, str)])

	def getTrimmedSequenceText(self, sequence):
		text = self.getSequenceText(sequence)
		if config.conf[CONFIG_SECTION]["trimWhitespaceFromStart"]:
			text = text.lstrip()
		if config.conf[CONFIG_SECTION]["trimWhitespaceFromEnd"]:
			text = text.rstrip()
		return text

	def copyHistoryItemText(self, item):
		text = self.getTrimmedSequenceText(item)

		postCopyAction = config.conf[CONFIG_SECTION]['postCopyAction']
		if api.copyToClip(text):
			if postCopyAction in (POST_COPY_BEEP, POST_COPY_BOTH):
				tones.beep(config.conf[CONFIG_SECTION]['beepFrequency'], config.conf[CONFIG_SECTION]['beepDuration'])
			if postCopyAction in (POST_COPY_SPEAK, POST_COPY_BOTH):
				# Translators: A short confirmation message spoken after copying a speech history item.
				self.oldSpeak([_('Copied')])

	__gestures = {
		'kb:f12': 'copyLast',
		'kb:shift+f11': 'prevString',
		'kb:shift+f12': 'nextString',
		'kb:NVDA+shift+f10': 'startRecording',
		'kb:NVDA+shift+f11': 'pauseRecording',
		'kb:NVDA+shift+f12': 'stopRecording',
		'kb:NVDA+h': 'showHistory',
		'kb:NVDA+shift+h': 'copyAllHistory',
		'kb:NVDA+control+h': 'clearHistory',
		'kb:NVDA+x': 'repeatMostRecentSpeech',
		'kb:NVDA+alt+h': 'copyMostRecentSpeech'
	}

