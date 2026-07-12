import wx
import addonHandler
import config
import tones
import os
from gui import guiHelper, nvdaControls
from gui.settingsDialogs import SettingsPanel
from .constants import (CONFIG_SECTION, MIN_HISTORY_ENTRIES, MAX_HISTORY_ENTRIES, POST_COPY_NOTHING, POST_COPY_BEEP, POST_COPY_SPEAK, POST_COPY_BOTH, DEFAULT_POST_COPY_ACTION, MIN_BEEP_FREQUENCY, MAX_BEEP_FREQUENCY, MIN_BEEP_DURATION, MAX_BEEP_DURATION)

addonHandler.initTranslation()

class SpeechHistorySettingsPanel(SettingsPanel):
	# Translators: the label/title for the Speech History settings panel.
	title = _('Speech History')

	def makeSettings(self, settingsSizer):
		mainHelper = guiHelper.BoxSizerHelper(self, sizer=settingsSizer)

		historySizer = wx.StaticBoxSizer(wx.StaticBox(self, label=_("History")), wx.VERTICAL)
		historyHelper = guiHelper.BoxSizerHelper(self, sizer=historySizer)

		copySizer = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Copy feedback")), wx.VERTICAL)
		copyHelper = guiHelper.BoxSizerHelper(self, sizer=copySizer)

		behaviorSizer = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Copy behavior")), wx.VERTICAL)
		behaviorHelper = guiHelper.BoxSizerHelper(self, sizer=behaviorSizer)

		self.loggingSizer = wx.StaticBoxSizer(wx.StaticBox(self, label=_("Speech output logging")), wx.VERTICAL)
		loggingHelper = guiHelper.BoxSizerHelper(self, sizer=self.loggingSizer)

		pathSizer = wx.BoxSizer(wx.HORIZONTAL)
		pathHelper = guiHelper.BoxSizerHelper(self, sizer=pathSizer)

		mainHelper.addItem(historySizer)
		mainHelper.addItem(copySizer)
		mainHelper.addItem(behaviorSizer)
		mainHelper.addItem(self.loggingSizer)
		loggingHelper.addItem(pathSizer)

		# Translators: the label for the preference to choose the maximum number of stored history entries
		maxHistoryLengthLabelText = _('&Maximum number of history entries (requires NVDA restart to take effect)')
		self.maxHistoryLengthEdit = historyHelper.addLabeledControl(maxHistoryLengthLabelText, nvdaControls.SelectOnFocusSpinCtrl, min=MIN_HISTORY_ENTRIES, max=MAX_HISTORY_ENTRIES, initial=config.conf[CONFIG_SECTION]['maxHistoryLength'])

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
		self.postCopyActionCombo = copyHelper.addLabeledControl(postCopyActionComboText, wx.Choice, choices=postCopyActionChoices)
		self.postCopyActionCombo.SetSelection(self.postCopyActionValues.index(config.conf[CONFIG_SECTION]['postCopyAction']))
		self.postCopyActionCombo.defaultValue = self.postCopyActionValues.index(DEFAULT_POST_COPY_ACTION)
		self.postCopyActionCombo.Bind(wx.EVT_CHOICE, lambda evt: self.refreshUI())

		# Translators: The label for the speech history setting controlling the frequency of the post-copy beep (in Hz).
		beepFrequencyLabelText = _('Beep &frequency (Hz)')
		self.beepFrequencyEdit = copyHelper.addLabeledControl(beepFrequencyLabelText, nvdaControls.SelectOnFocusSpinCtrl, min=MIN_BEEP_FREQUENCY, max=MAX_BEEP_FREQUENCY, initial=config.conf[CONFIG_SECTION]['beepFrequency'])

		# Translators: The label for the speech history setting controlling the length of the post-copy beep (in milliseconds).
		beepDurationLabelText = _('Beep &duration (ms)')
		self.beepDurationEdit = copyHelper.addLabeledControl(beepDurationLabelText, nvdaControls.SelectOnFocusSpinCtrl, min=MIN_BEEP_DURATION, max=MAX_BEEP_DURATION, initial=config.conf[CONFIG_SECTION]['beepDuration'])

		# Translators: The label of a button in the Speech History settings panel for playing a sample beep to test the user's chosen frequency and duration settings.
		self.beepButton = copyHelper.addItem(wx.Button(self, label=_('&Play example beep')))
		self.Bind(wx.EVT_BUTTON, self.onBeepButton, self.beepButton)

		# Translators: the label for the preference to beep when start or stop recording
		self.beepWhenStartOrStopRecordingCB = copyHelper.addItem(wx.CheckBox(self, label=_('&Beep when start or stop recording speech')))
		self.beepWhenStartOrStopRecordingCB.SetValue(config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record'])

		self.refreshUI()

		# Translators: The label for the preference to move cursor to last history item after copy
		self.moveCursorToLastItemCB = behaviorHelper.addItem(wx.CheckBox(self, label=_('Move cursor to last history item after copy')))
		self.moveCursorToLastItemCB.SetValue(config.conf[CONFIG_SECTION]['move_cursor_to_last_item_after_copy'])

		# Translators: the label for the preference to trim whitespace from the start of text
		self.trimWhitespaceFromStartCB = behaviorHelper.addItem(wx.CheckBox(self, label=_('Trim whitespace from &start when copying text')))
		self.trimWhitespaceFromStartCB.SetValue(config.conf[CONFIG_SECTION]['trimWhitespaceFromStart'])

		# Translators: the label for the preference to trim whitespace from the end of text
		self.trimWhitespaceFromEndCB = behaviorHelper.addItem(wx.CheckBox(self, label=_('Trim whitespace from &end when copying text')))
		self.trimWhitespaceFromEndCB.SetValue(config.conf[CONFIG_SECTION]['trimWhitespaceFromEnd'])

		# Translators: the label for write the NVDA's speech output go out a log file
		self.writeSpeechOutputCB = loggingHelper.addItem(wx.CheckBox(self, label=_("&Write the NVDA's speech output go out a log file")))
		self.Bind(wx.EVT_CHECKBOX, self.onCheckBox, self.writeSpeechOutputCB)
		self.writeSpeechOutputCB.SetValue(config.conf[CONFIG_SECTION]['write_nvda_speech_output_log_file'])

		# Translators: the label for the text box to select path for nvda's speech output log file
		nvdaSpeechOutputFileLabelText = _("NVDA's speech &output log file path")
		self.nvdaSpeechOutputFileEdit = pathHelper.addLabeledControl(nvdaSpeechOutputFileLabelText, wx.TextCtrl)
		self.nvdaSpeechOutputFileEdit.SetValue(config.conf[CONFIG_SECTION]['nvda_speech_output_log_file'])

		# Translators: the label for browse button to select path for NVDA's speech output
		self.browseButton = pathHelper.addItem(wx.Button(self, label=_('&Browse...')))
		self.Bind(wx.EVT_BUTTON, self.onBrowseButton, self.browseButton)

		# Translators: the label for a checkbox  to decide whether or not to add the current time to NVDA's speech output log file
		self.addCurrentTimeCB = loggingHelper.addItem(wx.CheckBox(self, label=_("Add current &time to NVDA's speech output log file")))
		self.addCurrentTimeCB.SetValue(config.conf[CONFIG_SECTION]['add_current_time_to_nvda_speech_output_log_file'])

		self.onCheckBox(None)

	def refreshUI(self):
		postCopyAction = self.postCopyActionValues[self.postCopyActionCombo.GetSelection()]
		enableBeepSettings = postCopyAction in (POST_COPY_BEEP, POST_COPY_BOTH)
		self.beepFrequencyEdit.Enable(enableBeepSettings)
		self.beepDurationEdit.Enable(enableBeepSettings)
		self.beepButton.Enable(enableBeepSettings)

	def onBeepButton(self, event):
		tones.beep(self.beepFrequencyEdit.GetValue(), self.beepDurationEdit.GetValue())

	def onCheckBox(self, event):
		status = self.writeSpeechOutputCB.GetValue()

		self.nvdaSpeechOutputFileEdit.Show(status)
		self.browseButton.Show(status)
		self.addCurrentTimeCB.Show(status)
		self.loggingSizer.Layout()
		self.Layout()

	def onBrowseButton(self, event):
		with wx.FileDialog(self, _('Save as...'), defaultDir=os.path.dirname(self.nvdaSpeechOutputFileEdit.GetValue()), defaultFile=os.path.basename(self.nvdaSpeechOutputFileEdit.GetValue()), wildcard='Log files (*.log)|*.log|Text files (*.txt)|*.txt|All files (*.*)|*.*', style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
			if dialog.ShowModal() == wx.ID_OK:
				self.nvdaSpeechOutputFileEdit.SetValue(dialog.GetPath())

	def onSave(self):
		config.conf[CONFIG_SECTION]['maxHistoryLength'] = self.maxHistoryLengthEdit.GetValue()
		config.conf[CONFIG_SECTION]['postCopyAction'] = self.postCopyActionValues[self.postCopyActionCombo.GetSelection()]
		config.conf[CONFIG_SECTION]['beepFrequency'] = self.beepFrequencyEdit.GetValue()
		config.conf[CONFIG_SECTION]['beepDuration'] = self.beepDurationEdit.GetValue()
		config.conf[CONFIG_SECTION]['beep_when_start_or_stop_record'] = self.beepWhenStartOrStopRecordingCB.GetValue()
		config.conf[CONFIG_SECTION]['move_cursor_to_last_item_after_copy'} = self.moveCursorToLastItemCB.GetValue()
		config.conf[CONFIG_SECTION]['trimWhitespaceFromStart'] = self.trimWhitespaceFromStartCB.GetValue()
		config.conf[CONFIG_SECTION]['trimWhitespaceFromEnd'] = self.trimWhitespaceFromEndCB.GetValue()
		config.conf[CONFIG_SECTION]['write_nvda_speech_output_log_file'] = self.writeSpeechOutputCB.GetValue()
		config.conf[CONFIG_SECTION]['nvda_speech_output_log_file'] = self.nvdaSpeechOutputFileEdit.GetValue()
		config.conf[CONFIG_SECTION]['add_current_time_to_nvda_speech_output_log_file'] = self.addCurrentTimeCB.GetValue()
