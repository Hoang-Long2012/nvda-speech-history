import wx
import addonHandler
import config
import tones
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsPanel
from .constants import (CONFIG_SECTION, MIN_HISTORY_ENTRIES, MAX_HISTORY_ENTRIES, POST_COPY_NOTHING, POST_COPY_BEEP, POST_COPY_SPEAK, POST_COPY_BOTH, DEFAULT_POST_COPY_ACTION, MIN_BEEP_FREQUENCY, MAX_BEEP_FREQUENCY, MIN_BEEP_DURATION, MAX_BEEP_DURATION)

addonHandler.initTranslation()

class SpeechHistorySettingsPanel(SettingsPanel):
	# Translators: the label/title for the Speech History settings panel.
	title = _('Speech History')

	def makeSettings(self, settingsSizer):
		helper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		# Translators: the label for the preference to choose the maximum number of stored history entries
		maxHistoryLengthLabelText = _('&Maximum number of history entries (requires NVDA restart to take effect)')
		self.maxHistoryLengthEdit = helper.addLabeledControl(maxHistoryLengthLabelText, nvdaControls.SelectOnFocusSpinCtrl, min=MIN_HISTORY_ENTRIES, max=MAX_HISTORY_ENTRIES, initial=config.conf[CONFIG_SECTION]['maxHistoryLength'])

		# Translators: The label for the preference of what to do after copying a speech history item to the clipboard. The options are "Do nothing", "Beep", "Speak", or "Beep and speak".
		postCopyActionComboText = _('&After copying speech:')
		postCopyActionChoices = [
			# Translators: A SpeechHistory option to have NVDA do nothing (no beep or speech) after copying a history item.
			_('Do nothing'),
			# Translators: A SpeechHistory option to have NVDA beep after copying a history item.
			_('Beep'),
			# Translators: A SpeechHistory option to have NVDA speak confirmation after copying a history item.
			_('Speak'),
			# Translators: A SpeechHistory option to have NVDA both beep and speak as confirmation after copying a history item.
			_('Both beep and speak'),
		]
		self.postCopyActionValues = (POST_COPY_NOTHING, POST_COPY_BEEP, POST_COPY_SPEAK, POST_COPY_BOTH)
		self.postCopyActionCombo = helper.addLabeledControl(postCopyActionComboText, wx.Choice, choices=postCopyActionChoices)
		self.postCopyActionCombo.SetSelection(self.postCopyActionValues.index(config.conf[CONFIG_SECTION]['postCopyAction']))
		self.postCopyActionCombo.defaultValue = self.postCopyActionValues.index(DEFAULT_POST_COPY_ACTION)
		self.postCopyActionCombo.Bind(wx.EVT_CHOICE, lambda evt: self.refreshUI())

		# Translators: The label for the speech history setting controlling the frequency of the post-copy beep (in Hz).
		beepFrequencyLabelText = _('Beep &frequency (Hz)')
		self.beepFrequencyEdit = helper.addLabeledControl(beepFrequencyLabelText, nvdaControls.SelectOnFocusSpinCtrl, min=MIN_BEEP_FREQUENCY, max=MAX_BEEP_FREQUENCY, initial=config.conf[CONFIG_SECTION]['beepFrequency'])

		# Translators: The label for the speech history setting controlling the length of the post-copy beep (in milliseconds).
		beepDurationLabelText = _('Beep &duration (ms)')
		self.beepDurationEdit = helper.addLabeledControl(beepDurationLabelText, nvdaControls.SelectOnFocusSpinCtrl, min=MIN_BEEP_DURATION, max=MAX_BEEP_DURATION, initial=config.conf[CONFIG_SECTION]['beepDuration'])

		# Translators: The label of a button in the Speech History settings panel for playing a sample beep to test the user's chosen frequency and duration settings.
		self.beepButton = helper.addItem(wx.Button(self, label=_('&Play example beep')))
		self.Bind(wx.EVT_BUTTON, self.onBeepButton, self.beepButton)

		self.refreshUI()

		# Translators: the label for the preference to trim whitespace from the start of text
		self.trimWhitespaceFromStartCB = helper.addItem(wx.CheckBox(self, label=_('Trim whitespace from &start when copying text')))
		self.trimWhitespaceFromStartCB.SetValue(config.conf[CONFIG_SECTION]['trimWhitespaceFromStart'])

		# Translators: the label for the preference to trim whitespace from the end of text
		self.trimWhitespaceFromEndCB = helper.addItem(wx.CheckBox(self, label=_('Trim whitespace from &end when copying text')))
		self.trimWhitespaceFromEndCB.SetValue(config.conf[CONFIG_SECTION]['trimWhitespaceFromEnd'])

		# Translators: the label for the preference to beep when start or stop recording
		self.beepWhenStartOrStopRecordingCB = helper.addItem(wx.CheckBox(self, label=_('&Beep when start or stop recording speech')))
		self.beepWhenStartOrStopRecordingCB.SetValue(config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record'])

	def refreshUI(self):
		postCopyAction = self.postCopyActionValues[self.postCopyActionCombo.GetSelection()]
		enableBeepSettings = postCopyAction in (POST_COPY_BEEP, POST_COPY_BOTH)
		self.beepFrequencyEdit.Enable(enableBeepSettings)
		self.beepDurationEdit.Enable(enableBeepSettings)
		self.beepButton.Enable(enableBeepSettings)

	def onBeepButton(self, event):
		tones.beep(self.beepFrequencyEdit.GetValue(), self.beepDurationEdit.GetValue())

	def onSave(self):
		config.conf[CONFIG_SECTION]['maxHistoryLength'] = self.maxHistoryLengthEdit.GetValue()
		config.conf[CONFIG_SECTION]['postCopyAction'] = self.postCopyActionValues[self.postCopyActionCombo.GetSelection()]
		config.conf[CONFIG_SECTION]['beepFrequency'] = self.beepFrequencyEdit.GetValue()
		config.conf[CONFIG_SECTION]['beepDuration'] = self.beepDurationEdit.GetValue()
		config.conf[CONFIG_SECTION]['trimWhitespaceFromStart'] = self.trimWhitespaceFromStartCB.GetValue()
		config.conf[CONFIG_SECTION]['trimWhitespaceFromEnd'] = self.trimWhitespaceFromEndCB.GetValue()
		config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record'] = self.beepWhenStartOrStopRecordingCB.GetValue()
