# NVDA Add-on: Speech History
# Copyright (C) 2012 Tyler Spivey
# Copyright (C) 2015-2025 James Scholes
# This add-on is free software, licensed under the terms of the GNU General Public License (version 2).
# See the file LICENSE for more details.

from collections import deque
from contextlib import contextmanager
from functools import wraps
from datetime import datetime
import addonHandler
import api
import config
import globalPluginHandler
import speech
import speechViewer
import tones
import ui
from queueHandler import queueFunction, eventQueue
from eventHandler import FocusLossCancellableSpeechCommand
from gui.settingsDialogs import NVDASettingsDialog
from scriptHandler import script, getLastScriptRepeatCount
from logHandler import log
from .settings import SpeechHistorySettingsPanel
from .constants import (CONFIG_SECTION, POST_COPY_BEEP, POST_COPY_SPEAK, POST_COPY_BOTH, MAX_SPELL_LENGTH, HTML_CONTAINER_START, HTML_CONTAINER_END, HTML_ITEM_START, HTML_ITEM_END, confspec, COMMAND_LAYER_GESTURES)

try:
	import nh3
	HTML_FORMAT_HISTORY_SUPPORTED = True
except ImportError:
	HTML_FORMAT_HISTORY_SUPPORTED = False


addonHandler.initTranslation()

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
		self.cursor = 0
		self._recorded = []
		self._recording = False
		self._record = False
		self.ignore_history = 0
		self.layer = False
		self.log = None
		self.logPath = None
		self.updateLogFile()
		self._initSpeechCapture()

	def _initSpeechCapture(self):
		if hasattr(speech, "pre_speechQueued"):
			speech.pre_speechQueued.register(self._onSpeechQueued)
			self.oldSpeak = speech.speech.speak
		elif hasattr(speech.speech, "pre_speech"):
			speech.speech.pre_speech.register(self._onSpeechQueued)
			self.oldSpeak = speech.speech.speak
		elif hasattr(speech, 'speak'):
			self.oldSpeak = speech.speak
			speech.speak = self.mySpeak
		elif hasattr(speech.speech, 'speak'):
			self.oldSpeak = speech.speech.speak
			speech.speech.speak = self.mySpeak
		else:
			log.error('Speech history not supported')
			ui.message(_('Speech history not supported'))

	# Translators: Documentation string for copy currently selected speech history item script
	@script(description=_('Press once to copy the currently selected speech history item to the clipboard, which by default will be the most recently spoken text by NVDA. Double press to copy the currently selected speech history item to the clipboard with whitespaces is trim.'), category=SCRIPT_CATEGORY)
	def script_copyLast(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return
		repeat = getLastScriptRepeatCount()
		trim = None
		if repeat == 1:
			trim = True
		else:
			trim = False
		self.copyHistoryItemText(self._history[self.history_pos], trim)

	# Translators: Documentation string for previous speech history item script
	@script(description=_('Review the previous item in NVDA\'s speech history.'), category=SCRIPT_CATEGORY)
	def script_prevString(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return
		self.history_pos += 1
		if self.history_pos > len(self._history) - 1:
			tones.beep(200, 100)
			self.history_pos -= 1
		self.speak(self._history[self.history_pos])
		self.cursor = 0

	# Translators: Documentation string for next speech history item script
	@script(description=_('Review the next item in NVDA\'s speech history.'), category=SCRIPT_CATEGORY)
	def script_nextString(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return
		self.history_pos -= 1
		if self.history_pos < 0:
			tones.beep(200, 100)
			self.history_pos += 1

		self.speak(self._history[self.history_pos])
		self.cursor = 0

	# Translators: Documentation string for start recording script
	@script(description=_('Start recording NVDA\'s speech output, for copying multiple announcements to the clipboard.'), category=SCRIPT_CATEGORY)
	def script_startRecording(self, gesture):
		if self._recording or self._record:
			# Translators: Message spoken when speech recording is already active
			tones.beep(200, 100)
			self.speak([_('Already recording speech')])
			return

		self._recording = True
		self._record = True
		if config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record']:
			tones.beep(1500, 80)
		# Translators: Message spoken when speech recording is started
		self.speak([_('Started recording speech')])
	script_startRecording.exit_on_press = True

	# Translators: Documentation string for stop recording script
	@script(description=_('Stop recording NVDA\'s speech output, and copy the recorded announcements to the clipboard.'), category=SCRIPT_CATEGORY)
	def script_stopRecording(self, gesture):
		if not self._recording:
			# Translators: Message spoken when speech recording is not already active
			tones.beep(200, 100)
			self.speak([_('Not currently recording speech')])
			return

		self._recording = False
		self._record = False
		if config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record']:
			tones.beep(800, 80)
		# Translators: Message spoken when speech recording is stopped
		self.speak([_('Recorded speech copied to clipboard')])
		api.copyToClip('\n'.join(self._recorded))
		self._recorded.clear()
	script_stopRecording.exit_on_press = True

	# Translators: Documentation string for pause recording script
	@script(description=_('Pause recording NVDA\'s speech output, and copy the recorded announcements to the clipboard.'), category=SCRIPT_CATEGORY)
	def script_pauseRecording(self, gesture):
		if not self._record:
			# Translators: Message spoken when not recording speech
			self.speak([_('Not currently recording speech')])
			tones.beep(200, 100)
			return

		if self._recording:
			self._recording = False
			if config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record']:
				tones.beep(800, 80)

			# Translators: Message spoken when speech recording is paused
			self.speak([_('Paused recording speech')])
		else:
			self._recording = True
			if config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record']:
				tones.beep(1500, 80)

			# Translators: Message spoken when speech recording is restarted
			self.speak([_('Recording speech restarted')])
	script_pauseRecording.exit_on_press = True

	# Translators: Documentation string for show speech history script
	@script(description=_("Show NVDA's speech history in a browseable list."), category=SCRIPT_CATEGORY)
	def script_showHistory(self, gesture):
		if not self._history:
			# Translators: A message shown when users try to view their speech history but it's empty.
			self.speak([_('No history items.')])
			tones.beep(200, 100)
			return

		if not HTML_FORMAT_HISTORY_SUPPORTED:
			# Translators: A message shown when HTML formatting is unavailable for speech history.
			self.speak([_('Warning: HTML formatting is unavailable. Showing speech history as plain text.')])

		message = makeHTMLList((self.getSequenceText(item) for item in self._history))

		# Translators: The title of the speech history window.
		title = _('Speech History')

		try:
			# HTML history items are already sanitized above.
			ui.browseableMessage(message=message, title=title, isHtml=HTML_FORMAT_HISTORY_SUPPORTED, copyButton=True, closeButton=True, sanitizeHtmlFunc=lambda string: string)
		except TypeError:
			ui.browseableMessage(message=message, title=title, isHtml=HTML_FORMAT_HISTORY_SUPPORTED, copyButton=True, closeButton=True)
	script_showHistory.exit_on_press = True

	# Translators: Documentation string for copy all speech history script
	@script(description=_("Copy all NVDA's speech history to clipboard."), category=SCRIPT_CATEGORY)
	def script_copyAllHistory(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
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
				self.speak([_('All history copied')])

	# Translators: Documentation string for clear all speech history script
	@script(description=_("Clear all NVDA's speech history."), category=SCRIPT_CATEGORY)
	def script_clearHistory(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return
		self._history.clear()
		self.history_pos = 0
		self.speak([_('History cleared')])

	# Translators: Documentation string for Repeat what NVDA just said script
	@script(description=_("Press once to repeat what NVDA just said, double to spell and triple to show in a browseable dialog."), category=SCRIPT_CATEGORY)
	def script_repeatMostRecentSpeech(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return

		repeat = getLastScriptRepeatCount()
		if repeat == 1:
			text = self.getTrimmedSequenceText(self._history[0])
			if not text:
				self.speak([_("No text to spell")])
				return
			if len(text) > MAX_SPELL_LENGTH:
				self.speak([_('The text is too long. It contains {} characters.').format(len(text))])
				return
			with self.suppressHistory():
				speech.speakSpelling(text)
		elif repeat == 2:
			ui.browseableMessage(message=self.getTrimmedSequenceText(self._history[0]), copyButton=True, closeButton=True)
		else:
			self.speak(self._history[0])

	# Translators: Documentation string for copy  most recently NVDA's speech to clipboard script
	@script(description=_("Copy most recently NVDA's speech to clipboard."), category=SCRIPT_CATEGORY)
	def script_copyMostRecentSpeech(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return

		self.copyHistoryItemText(self._history[0])

	# Translators: Documentation string for    move to beginning speech history item script
	@script(description=_('Review the beginning item in NVDA\'s speech history.'), category=SCRIPT_CATEGORY)
	def script_beginningString(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return

		self.history_pos = 0
		self.cursor = 0
		self.speak(self._history[self.history_pos])
		tones.beep(200, 100)

	# Translators: Documentation string for move to last speech history item script
	@script(description=_('Review the last item in NVDA\'s speech history.'), category=SCRIPT_CATEGORY)
	def script_lastString(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return

		self.history_pos = len(self._history) - 1
		self.cursor = 0
		self.speak(self._history[self.history_pos])
		tones.beep(200, 100)

	# Translators: Documentation string for move to next character of current speech history item script
	@script(description=_('Review the next character of current speech history item.'), category=SCRIPT_CATEGORY)
	def script_nextChar(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return
		self.cursor += 1
		if self.cursor > len(self.getSequenceText(self._history[self.history_pos])) - 1:
			tones.beep(200, 100)
			self.cursor -= 1
		with self.suppressHistory():
			speech.speakTypedCharacters(self.getSequenceText(self._history[self.history_pos])[self.cursor])

	# Translators: Documentation string for move to previous character of current speech history item script
	@script(description=_('Review the previous character of current speech history item.'), category=SCRIPT_CATEGORY)
	def script_prevChar(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return
		self.cursor -= 1
		if self.cursor < 0:
			tones.beep(200, 100)
			self.cursor += 1
		with self.suppressHistory():
			speech.speakTypedCharacters(self.getSequenceText(self._history[self.history_pos])[self.cursor])

# Translators: Documentation string for    move to beginning character of current speech history item script
	@script(description=_('Review the beginning character of current speech history item.'), category=SCRIPT_CATEGORY)
	def script_beginningChar(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return

		self.cursor = 0
		with self.suppressHistory():
			speech.speakTypedCharacters(self.getSequenceText(self._history[self.history_pos])[self.cursor])
		tones.beep(200, 100)

	# Translators: Documentation string for move to last character of current speech history item script
	@script(description=_('Review the last character of current speech history item.'), category=SCRIPT_CATEGORY)
	def script_lastChar(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return

		self.cursor = len(self.getSequenceText(self._history[self.history_pos])) - 1
		with self.suppressHistory():
			speech.speakTypedCharacters(self.getSequenceText(self._history[self.history_pos])[self.cursor])
		tones.beep(200, 100)

	# Translators: Documentation string for copy current speech history item character script
	@script(description=_('Copy current speech history item character.'), category=SCRIPT_CATEGORY)
	def script_copyChar(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return

		self.copyHistoryItemText([self.getSequenceText(self._history[self.history_pos])[self.cursor]])

	# Translators: Documentation string for remove current speech history item script
	@script(description=_('Remove current speech history item.'), category=SCRIPT_CATEGORY)
	def script_removeCurrentItem(self, gesture):
		if not self._history:
			self.speak([_("No history items")])
			tones.beep(200, 100)
			return

		history = list(self._history)
		del history[self.history_pos]
		self._history = deque(history, maxlen=config.conf[CONFIG_SECTION]['maxHistoryLength'])
		if self.history_pos != 0:
			self.history_pos -= 1
		self.cursor = 0
		self.speak([_('Item deleted')])

	# Translators: Documentation string for Speech History command layer help script
	@script(description=_('Speech History command layer help.'), category=SCRIPT_CATEGORY)
	def script_speechHistoryCommandLayerHelp(self, gesture):
		lines = []

		for gestureName, scriptName in COMMAND_LAYER_GESTURES.items():
			script = getattr(self, "script_" + scriptName, None)

			if script:
				description = script.__doc__ or _("No description")
			else:
				description = _("No description")
			lines.append(f"{gestureName[3:].title()}: {description}")

		message = "\n".join(lines)

		ui.browseableMessage(message=message, title=_("Speech History command layer help"), copyButton=True, closeButton=True)
	script_speechHistoryCommandLayerHelp.exit_on_press = True

	# Translators: Document string for Speech History command layer script
	@script(description=_('Activate Speech History command layer.'), category=SCRIPT_CATEGORY)
	def script_SpeechHistoryCommandLayer(self, gesture):
		if self.layer:
			tones.beep(200, 100)
			return

		self.layer = True
		self.bindGestures(COMMAND_LAYER_GESTURES)
		tones.beep(400, 100)

	def script_exitCommandLayer(self, gesture):
		"""Exit the command layer."""
		self.speak([_('Canceled')])
		tones.beep(200, 100)
	script_exitCommandLayer.exit_on_press = True

	def script_commandLayerError(self, gesture):
		self.speak([_('Unknown key: {}').format(gesture.displayName)])
		tones.beep(200, 100)

	def finish(self):
		if not self.layer:
			return

		self.layer = False
		self.clearGestureBindings()
		self.bindGestures(self.__gestures)

	def terminate(self, *args, **kwargs):
		if self.log:
			self.log.close()
			self.log = None
			self.logPath = None

		if hasattr(speech, "pre_speechQueued"):
			speech.pre_speechQueued.unregister(self._onSpeechQueued)
		elif hasattr(speech.speech, "pre_speech"):
			speech.speech.pre_speech.unregister(self._onSpeechQueued)
		elif hasattr(speech, 'speak'):
			speech.speak = self.oldSpeak
		elif hasattr(speech.speech, 'speak'):
			speech.speech.speak = self.oldSpeak

		if SpeechHistorySettingsPanel in NVDASettingsDialog.categoryClasses:
			NVDASettingsDialog.categoryClasses.remove(SpeechHistorySettingsPanel)

		super().terminate(*args, **kwargs)

	def getScript(self, gesture):
		if not self.layer:
			return super().getScript(gesture)

		script = super().getScript(gesture)

		if not script:
			return finally_(self.script_commandLayerError, self.finish)

		if not getattr(script, 'exit_on_press', False):
			return script

		return finally_(script, self.finish)

	def append_to_history(self, seq):
		seq = [command for command in seq if not isinstance(command, FocusLossCancellableSpeechCommand)]
		self._history.appendleft(seq)
		self.history_pos = 0
		if self._recording:
			self._recorded.append(self.getTrimmedSequenceText(seq))
		if config.conf[CONFIG_SECTION]["write_nvda_speech_output_log_file"]:
			self.updateLogFile(f'{self.getTrimmedSequenceText(seq)}\n')

	def _onSpeechQueued(self, speechSequence, priority, *args, **kwargs):
		if self.ignore_history:
			return

		text = self.getSequenceText(speechSequence)
		if text.strip():
			queueFunction(eventQueue, self.append_to_history, speechSequence)

	def mySpeak(self, sequence, *args, **kwargs):
		self.oldSpeak(sequence, *args, **kwargs)
		if self.ignore_history:
			return
		text = self.getSequenceText(sequence)
		if text.strip():
			queueFunction(eventQueue, self.append_to_history, sequence)

	def getSequenceText(self, sequence):
		return speechViewer.SPEECH_ITEM_SEPARATOR.join([x for x in sequence if isinstance(x, str)])

	def getTrimmedSequenceText(self, sequence, trim=None):
		text = self.getSequenceText(sequence)
		if not trim:
			if config.conf[CONFIG_SECTION]["trimWhitespaceFromStart"]:
				text = text.lstrip()
			if config.conf[CONFIG_SECTION]["trimWhitespaceFromEnd"]:
				text = text.rstrip()
		else:
			text = text.strip()
		return text

	@contextmanager
	def suppressHistory(self):
		self.ignore_history += 1
		try:
			yield
		finally:
			self.ignore_history -= 1

	def speak(self, sequence, *args, **kwargs):
		with self.suppressHistory():
			self.oldSpeak(sequence, *args, **kwargs)

	def copyHistoryItemText(self, item, trim=None):
		text = self.getTrimmedSequenceText(item, trim=trim)

		postCopyAction = config.conf[CONFIG_SECTION]['postCopyAction']
		if api.copyToClip(text):
			if postCopyAction in (POST_COPY_BEEP, POST_COPY_BOTH):
				tones.beep(config.conf[CONFIG_SECTION]['beepFrequency'], config.conf[CONFIG_SECTION]['beepDuration'])
			if postCopyAction in (POST_COPY_SPEAK, POST_COPY_BOTH):
				# Translators: A short confirmation message spoken after copying a speech history item.
				self.speak([_('Copied')])
			if config.conf[CONFIG_SECTION]['move_cursor_to_last_item_after_copy']:
				self.history_pos = 0

	def updateLogFile(self, text=None):
		enabled = config.conf[CONFIG_SECTION]["write_nvda_speech_output_log_file"]
		path = config.conf[CONFIG_SECTION]["nvda_speech_output_log_file"]

		if enabled:
			if self.log is None or self.logPath != path:
				if self.log:
					self.log.close()
					self.log = None
					self.logPath = None
				try:
					self.log = open(config.conf[CONFIG_SECTION]["nvda_speech_output_log_file"], "a", encoding="utf-8")
					self.logPath = path
				except Exception:
					log.exception("Cannot open speech output log")
					self.log = None
					self.logPath = None
			if text and self.log:
				if config.conf[CONFIG_SECTION]["add_current_time_to_nvda_speech_output_log_file"]:
					now = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
					string = f'{now} - {text}'
				else:
					string = text
				self.log.write(string)
				self.log.flush()
		else:
			if self.log:
				self.log.close()
				self.log = None
				self.logPath = None

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
