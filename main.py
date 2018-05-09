import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import Button
import wave
import numpy as np
from collections import namedtuple
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2TkAgg
from matplotlib.figure import Figure

import re

import sys

import os.path
from os import listdir


import json

from pydub import AudioSegment

from scipy.signal import hilbert

import math

import pyaudio
import binascii
import struct

from pympler.tracker import SummaryTracker
tracker = SummaryTracker()

import sounddevice as sd

#print(sd.query_devices())

import scipy.fftpack
import scipy.stats

# https://stackoverflow.com/questions/39458337/is-there-a-way-to-add-close-buttons-to-tabs-in-tkinter-ttk-notebook
class CustomNotebook(ttk.Notebook):
    """A ttk Notebook with close buttons on each tab"""

    __initialized = False

    def __init__(self, *args, **kwargs):
        if not self.__initialized:
            self.__initialize_custom_style()
            self.__inititialized = True

        kwargs["style"] = "CustomNotebook"
        ttk.Notebook.__init__(self, *args, **kwargs)

        self._active = None

        self.bind("<ButtonPress-1>", self.on_close_press, True)
        self.bind("<ButtonRelease-1>", self.on_close_release)

    def on_close_press(self, event):
        """Called when the button is pressed over the close button"""

        element = self.identify(event.x, event.y)

        if "close" in element:
            index = self.index("@%d,%d" % (event.x, event.y))
            self.state(['pressed'])
            self._active = index

    def on_close_release(self, event):
        """Called when the button is released over the close button"""
        if not self.instate(['pressed']):
            return

        element =  self.identify(event.x, event.y)
        index = self.index("@%d,%d" % (event.x, event.y))

        if "close" in element and self._active == index:
            self.forget(index)
            self.event_generate("<<NotebookTabClosed>>")

        self.state(["!pressed"])
        self._active = None

    def __initialize_custom_style(self):
        style = ttk.Style()
        self.images = (
            tk.PhotoImage("img_close", data='''
                R0lGODlhCAAIAMIBAAAAADs7O4+Pj9nZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
                d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
                5kEJADs=
                '''),
            tk.PhotoImage("img_closeactive", data='''
                R0lGODlhCAAIAMIEAAAAAP/SAP/bNNnZ2cbGxsbGxsbGxsbGxiH5BAEKAAQALAAA
                AAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU5kEJADs=
                '''),
            tk.PhotoImage("img_closepressed", data='''
                R0lGODlhCAAIAMIEAAAAAOUqKv9mZtnZ2Ts7Ozs7Ozs7Ozs7OyH+EUNyZWF0ZWQg
                d2l0aCBHSU1QACH5BAEKAAQALAAAAAAIAAgAAAMVGDBEA0qNJyGw7AmxmuaZhWEU
                5kEJADs=
            ''')
        )

        style.element_create("close", "image", "img_close",
                            ("active", "pressed", "!disabled", "img_closepressed"),
                            ("active", "!disabled", "img_closeactive"), border=8, sticky='')
        style.layout("CustomNotebook", [("CustomNotebook.client", {"sticky": "nswe"})])
        style.layout("CustomNotebook.Tab", [
            ("CustomNotebook.tab", {
                "sticky": "nswe", 
                "children": [
                    ("CustomNotebook.padding", {
                        "side": "top", 
                        "sticky": "nswe",
                        "children": [
                            ("CustomNotebook.focus", {
                                "side": "top", 
                                "sticky": "nswe",
                                "children": [
                                    ("CustomNotebook.label", {"side": "left", "sticky": ''}),
                                    ("CustomNotebook.close", {"side": "left", "sticky": ''}),
                                ]
                        })
                    ]
                })
            ]
        })
    ])

A4_freq = 440.0
A4_midi_number = 69
C4_midi_number = 60
notes_per_octave = 12
note_names = np.array(['C', 'Cs', 'D', 'Ds', 'E', 'F', 'Fs', 'G', 'Gs', 'A', 'As', 'B'])

def FreqToNote(freq):

	midi_number = round(A4_midi_number + notes_per_octave * math.log(freq / A4_freq, 2))
	
	relative_midi_number_C4 = midi_number - C4_midi_number

	note_name = note_names[relative_midi_number_C4 % notes_per_octave]
	note_octave = int(4 + relative_midi_number_C4 / notes_per_octave)

	return '{}{}'.format(note_name, note_octave)

def MidiNumberToFreq(midi_number):
	return pow(2, (midi_number - A4_midi_number) / notes_per_octave) * A4_freq

def NoteToFreq(name, octave):
	#l = np.array([1, 2, 3])
	#print(np.where(l == 1)[0])
	#print(np.nonzero(note_names == name))
	midi_number = C4_midi_number + (octave - 4) * notes_per_octave + np.where(note_names == name)[0][0]
	f = pow(2, (midi_number - A4_midi_number) / notes_per_octave) * A4_freq

	#print(f)
	return f

#for midi_number in np.arange(21, 108):
#	print("{} -> {}".format(midi_number, MidiNumberToFreq(midi_number)))

#for octave_number in np.arange(0, 9):
#	for note_name in note_names:
#		print("{}{} -> {}".format(note_name, octave_number, NoteToFreq(note_name, octave_number)))

def FindPeak(array):
	pass

np.set_printoptions(threshold=np.inf)

root = tk.Tk()
root.attributes('-zoomed', True)
root.title("Instrument Identification")
notebook = CustomNotebook(width=200, height=200)
notebook.pack(side="top", fill="both", expand=True)

file = {}
fft_raw_data = []

chunk = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
SAMPLE_RATE = 44100

A0_freq = 27.5

class Waveform:
	def RecordFromMicrophone(self):
		p = pyaudio.PyAudio()
		stream = p.open(format				= FORMAT,
						channels			= CHANNELS,
						rate				= SAMPLE_RATE,
						input				= True,
						frames_per_buffer	= chunk)

		mic_data = []
		chunk_count = int(SAMPLE_RATE / chunk * 4.0)

		for i in range(0, chunk_count):
			data = stream.read(chunk)
			mic_data.append(data)

		stream.stop_stream()
		stream.close()
		p.terminate()

		raw_bytes = b''.join(mic_data) # flatten mic_data to a list of bytes

		# This only supports mono atm
		raw_samples = [] # to store mic_data encoded as 16-bit signed integers
		#print(str(len(mic_data[2*i:(2*i)+2])))
		for i in range(0, len(raw_bytes) // 2):
			raw_samples += struct.unpack('<h', raw_bytes[2*i:(2*i)+2])

		self.channel_count 		= CHANNELS
		self.sample_width 		= 2 # 16 bits
		self.sampling_frequency	= SAMPLE_RATE
		self.frame_count		= len(raw_samples)

		if(self.channel_count == 1):
			self.time_samples = raw_samples		

		self.sample_count = len(self.time_samples)
		self.times = [k / self.sampling_frequency for k in range(self.sample_count)]
		T = self.sample_count / self.sampling_frequency
		self.freqs = [k / (2 * T) for k in range(self.sample_count)]


		if(self.sample_width < 1 or self.sample_width > 4):
			print("Audio file sample width is not supported. Only 8-, 16-, 24-, and 32-bit WAV and MP3 files are currently supported. Undefined behavior may follow.")

		self.trimmed_time_samples, self.trim_start, self.trim_end = self.Trim()	

	def LoadFromFile(self, file_path):
		self.file_path = file_path

		if file_path[-4:].lower() == '.wav':
			print("Loading .wav file: {}".format(file_path))

			wav_file = wave.open(file_path, 'rb')

			self.channel_count 		= wav_file.getnchannels()
			self.sample_width 		= wav_file.getsampwidth()
			self.sampling_frequency	= wav_file.getframerate()
			self.frame_count		= wav_file.getnframes()

			raw_bytes = np.fromstring(wav_file.readframes(-1), 'Int8') # encode raw byte data as an array of signed 8-bit integers
			raw_samples = SampleWidthDataFromBytes(raw_bytes, self.sample_width)

			wav_file.close()
		elif file_path[-4:].lower() == '.mp3':
			print("Loading .mp3 file: {}".format(file_path))

			mp3_file = AudioSegment.from_file(file_path, format='mp3')

			self.channel_count = mp3_file.channels
			self.sample_width = mp3_file.sample_width
			self.sampling_frequency = mp3_file.frame_rate
			self.frame_count = mp3_file.frame_count

			raw_samples = mp3_file.get_array_of_samples()
		else:
			print("Only .wav and .mp3 files are currently supported.")
			return

		if(self.channel_count == 1):
			self.time_samples = raw_samples
		elif(self.channel_count == 2):
			left_channel = raw_samples[::2]
			right_channel = raw_samples[1::2]
			
			assert(len(left_channel) == len(right_channel))

			self.time_samples = [(left_channel[i] + right_channel[i]) * 0.5 for i in range(len(left_channel))]
		else:
			print("Audio files with more than 2 channels are not supported.")

		self.sample_count = len(self.time_samples)
		self.times = [k / self.sampling_frequency for k in range(self.sample_count)]
		T = self.sample_count / self.sampling_frequency
		self.freqs = [k / (2 * T) for k in range(self.sample_count)]

		#print("F_s={}".format(self.sampling_frequency))

		if(self.sample_width < 1 or self.sample_width > 4):
			print("Audio file sample width is not supported. Only 8-, 16-, 24-, and 32-bit WAV and MP3 files are currently supported. Undefined behavior may follow.")

		self.trimmed_time_samples, self.trim_start, self.trim_end = self.Trim()

	def GetWaveform(self):
		return self.time_samples, self.times

	def GetSTFT(self):
		f, t, Zxx = scipy.signal.stft(self.trimmed_time_samples, self.sampling_frequency, nperseg=pow(2,16))
		
		averaged_stft = AverageSTFT(Zxx)

		#print(len(averaged_stft))

		return averaged_stft, f

	def GetFFT(self):
		#sample_count = len(self.time_samples)

		#k = np.arange(sample_count)
		#t = k / self.sampling_frequency
		#T = sample_count / self.sampling_frequency
		#frq = k / T

		self.freq_samples = abs(scipy.fftpack.rfft(self.time_samples))

		return self.freq_samples, self.freqs

	def GetTrimmedWaveform(self):
		return self.trimmed_time_samples, [x / self.sampling_frequency for x in range(len(self.trimmed_time_samples))]
		
	def GetTrimmedFFT(self):
		#sample_count = len(self.trimmed_time_samples)

		#k = np.arange(sample_count)
		#t = k / self.sampling_frequency
		#T = sample_count / self.sampling_frequency
		#frq = k / T

		self.freq_samples = abs(scipy.fftpack.rfft(self.trimmed_time_samples, self.sample_count))

		return self.freq_samples, self.freqs

	# Returns a slice of the waveform in time domain from start_time (in seconds) to end_time (in seconds)
	def GetTimeSlice(self, start_time, end_time):
		start_k = int(start_time * self.sampling_frequency)
		end_k = int(end_time * self.sampling_frequency)

		k_count = end_k - start_k

		return self.time_samples[start_k:end_k], [start_time + k / self.sampling_frequency for k in range(k_count)]

	#def GetSliceFFTByIndex(self, start_index, end_index):
		

	def GetSliceFFT(self, start_time, end_time):
		time_interval = end_time - start_time
		sample_count = time_interval * self.sampling_frequency

		k = np.arange(sample_count)
		t = start_time + k / self.sampling_frequency
		T = sample_count / self.sampling_frequency
		frq = k / T

		#self.t = self.k / self.sampling_frequency # Creates discrete array of time values for our sampling frequency		
		#self.k = np.arange(self.frame_count)
		#self.T = self.frame_count / self.sampling_frequency # Sample length in seconds
		#self.frq = self.k / self.T

		freq_samples = abs(scipy.fftpack.fft(self.GetTimeSlice(start_time, end_time)))

		#print(freq_samples)

		if len(frq) > len(freq_samples):
			frq = frq[:-1]
		if len(frq) < len(freq_samples):
			freq_samples[:-1]

		return freq_samples[0][:2000], frq[:2000]

	# Find the closest corresponding index in the frequency domain array for the given freq
	def FreqToIndex(self, target_freq):
		index = None
		for i, _ in enumerate(self.freqs[1:]):
			if self.freqs[i-1] < target_freq and self.freqs[i] > target_freq:
				if abs(self.freqs[i-1] - target_freq) < abs(self.freqs[i] - target_freq):
					index = i-1
				else:
					index = i

		if index == None:
			return 0
			print("Tried to convert invalid frequency to index")
		else:
			return index

	def IndexToFreq(self, target_index):
		return self.freqs[int(target_index)]

	# Trim portions of the time domain samples to remove beginning and ending silence as well as maybe some of the attack and release.
	def Trim(self):
		attack_amplitude_threshold = 0.10
		release_amplitude_threshold = 0.10
		anomaly_threshold = 1000
		wave_start_index, wave_end_index = None, None

#		hilbert = np.abs(scipy.signal.hilbert(self.time_samples))
#		b, a = scipy.signal.butter(3, 0.001, btype='lowpass') # 24Hz (for 48k sample rate) 3rd order Butterworth lowpass filter
#		zi = scipy.signal.lfilter_zi(b, a)
#		zi = zi * self.time_samples[0]
#		self.characteristic_signal = scipy.signal.filtfilt(b, a, hilbert)

		rectified_signal = np.abs(self.time_samples)
		b, a = scipy.signal.butter(3, self.FreqToNyquistRatio(100), btype='lowpass') # 24Hz (for 48k sample rate) 3rd order Butterworth lowpass filter
		zi = scipy.signal.lfilter_zi(b, a)
		zi = zi * self.time_samples[0]	
		self.characteristic_signal = scipy.signal.filtfilt(b, a, rectified_signal)

		# First, we find the max amplitude of the characteristic signal
		max_amplitude = np.amax(self.characteristic_signal)
		min_amplitude = np.amin(self.characteristic_signal)

		anomaly_count = 0

		for index, sample in enumerate(self.characteristic_signal):
			if wave_start_index == None:			
				#if (abs(sample) > amplitude_threshold * max_amplitude) or (abs(sample) < amplitude_threshold * min_amplitude):
				if (abs(sample) > attack_amplitude_threshold * max_amplitude):
					anomaly_count += 1
					#print("index={}; abs(sample)={}; anomalies={}".format(index, abs(sample), anomaly_count))
				else:
					anomaly_count = 0

				if anomaly_count >= anomaly_threshold:
					wave_start_index = index - anomaly_threshold + 1
					anomaly_count = 0
			elif wave_end_index == None:
				#if (abs(sample) < amplitude_threshold * max_amplitude) and (abs(sample) > amplitude_threshold * min_amplitude):
				if (abs(sample) < release_amplitude_threshold * max_amplitude):
					anomaly_count += 1
					#print("index={}; abs(sample)={}; anomalies={}".format(index, abs(sample), anomaly_count))
				else:
					anomaly_count = 0

				if anomaly_count >= anomaly_threshold:
					wave_end_index = index - anomaly_threshold + 1
					anomaly_count = 0
					break

		if wave_start_index == None:
			wave_start_index = 0
		if wave_end_index == None:
			wave_end_index = len(self.time_samples)

		#print("untrimmed length={}".format(len(self.time_samples)))
		#print("wave_start_index={}".format(wave_start_index))
		#print("wave_end_index={}".format(wave_end_index))
		#print("max_amplitude={}".format(max_amplitude))

		return self.time_samples[wave_start_index:wave_end_index], wave_start_index / self.sampling_frequency, wave_end_index / self.sampling_frequency

	def FreqToNyquistRatio(self, freq):
		nyquist_freq = self.sampling_frequency / 2
		return freq / nyquist_freq

	def FindStableWaveform(self):
		variation_threshold = 0.2
		global_amplitude_threshold = 0.25

		# We probably need at least 10 full wavelengths for now. With a low-end of 100Hz, that gives us 100 waveforms per second => 10 waveforms per 0.1 seconds.
		# So a 0.1 second window should work.
		sample_window_width = int(0.1 * self.sampling_frequency)

		global_max = np.amax(self.characteristic_signal)

		for i in range(len(self.characteristic_signal) - sample_window_width):
			subset = self.characteristic_signal[i:i + sample_window_width - 1]
			max_value = np.amax(subset)
			min_value = np.amin(subset)
			average_value = np.average(subset)

			if average_value >= global_amplitude_threshold * global_max:
				if (max_value - min_value) / average_value <= variation_threshold:
					return self.time_samples[i:i + sample_window_width - 1], self.times[i:i + sample_window_width - 1]

		print("Unable to find stable sub-waveform in waveform.")
		return [], []

	def DetectFreqPeaks(self, rising_threshold = 0.01, falling_threshold = 0.75, peak_amplitude_threshold_ratio = 0.01):
		try:
			self.freq_samples
		except:
			self.GetTrimmedFFT()

		window_width = 1000
		window_std = A0_freq
		window = scipy.signal.gaussian(window_width, window_std)
		self.convolved_fft = scipy.signal.convolve(self.freq_samples, window, mode='same')


		rising_trigger_value = np.max(self.convolved_fft) * rising_threshold
		amplitude_threshold_value = peak_amplitude_threshold_ratio * np.amax(self.freq_samples)

		convolved_slope = np.diff(self.convolved_fft)

		#print("len(convolved)={}; len(slope)={}".format(len(self.convolved_fft), len(convolved_slope)))

		self.peak_freq_indices = []
		self.begin_threshold_indices = []
		self.end_threshold_indices = []

		threshold_activated = False
		convolved_local_max = -1

		for index, convolved_value in enumerate(self.convolved_fft[:-1]):
			#print(self.freqs[:10])
			if convolved_value >= rising_trigger_value and not threshold_activated and convolved_slope[index] > 0:
				start_index = index

				threshold_activated = True				
				self.begin_threshold_indices.append(index)

			if convolved_value <= falling_threshold * convolved_local_max and threshold_activated and convolved_slope[index] < 0:
				end_index = index
				max_index = start_index + np.argmax(self.freq_samples[start_index:end_index])
				data_local_max = self.freq_samples[max_index]
				if data_local_max >= amplitude_threshold_value and self.freqs[max_index] >= A0_freq:
					#print("index = {}; freqs[index] = {}".format(start_index + np.argmax(self.freq_samples[start_index:end_index]), self.freqs[index]))
					self.peak_freq_indices.append(max_index)

				threshold_activated = False
				self.end_threshold_indices.append(index)
				convolved_local_max = -1

			if threshold_activated:
				if convolved_value > convolved_local_max:
					convolved_local_max = convolved_value

		return self.peak_freq_indices

	def GeneratePlots(self, debug_plots = False):
		try:
			self.freq_samples
		except:
			self.GetTrimmedFFT()

		try:
			self.peak_indices
		except:
			self.DetectFreqPeaks()

		try:
			self.fundamental_freq
		except:
			self.DetectFundamental()

		fig, (ax_time, ax_freq) = plt.subplots(2, 1)

		ax_time.plot(self.times, self.time_samples)
		ax_time.set_xlim(xmin = 0, xmax = self.times[-1])	
		if debug_plots == True:
			ax_time.plot(self.times, self.characteristic_signal, color='orange')
			ax_time.axvline(self.trim_start, color='red')
			ax_time.axvline(self.trim_end, color='red')
			ax_time.axhline(color='purple', linewidth=0.8)

		if len(self.peak_freq_indices) > 0:
			peak_freqs = [self.freqs[i] for i in self.peak_freq_indices]
			peak_amplitudes = [self.freq_samples[i] for i in self.peak_freq_indices]
			max_peak_amplitude = np.amax(self.freq_samples)
			peak_ratios = [k / max_peak_amplitude for k in peak_amplitudes]
	
			ax_freq.plot(self.freqs, self.freq_samples)
			ax_freq.set_xlim(xmin = 0, xmax = self.freqs[self.peak_freq_indices[-1]] * 1.2)
			ax_freq.set_ylim(ymin = 0, ymax = np.amax(self.freq_samples) * 1.2)
	
			ax_freq.scatter(peak_freqs, peak_amplitudes, color='purple', marker='o', s=8, zorder=10)
			annotate_font = {'size': 8}
			matplotlib.rc('font', **annotate_font)
			for i, peak_freq in enumerate(peak_freqs):
				if peak_freq == self.fundamental_freq:
					ax_freq.annotate("{:.1f}\n({:.2f})".format(peak_freqs[i], peak_ratios[i]), xy=(peak_freqs[i], peak_amplitudes[i]), xytext=(5, 0), textcoords='offset pixels', color='red')
				else:
					ax_freq.annotate("{:.1f}\n({:.2f})".format(peak_freqs[i], peak_ratios[i]), xy=(peak_freqs[i], peak_amplitudes[i]), xytext=(5, 0), textcoords='offset pixels')
	
		if debug_plots == True:
			ax_freq.plot(self.freqs, self.convolved_fft)

			begin_threshold_freqs = [self.freqs[i] for i in self.begin_threshold_indices]
			end_threshold_freqs = [self.freqs[i] for i in self.end_threshold_indices]		
			begin_threshold_amplitudes = [self.convolved_fft[i] for i in self.begin_threshold_indices]
			end_threshold_amplitudes = [self.convolved_fft[i] for i in self.end_threshold_indices]
			ax_freq.scatter(begin_threshold_freqs, begin_threshold_amplitudes , color='green', marker='^', s=8, zorder=13)
			ax_freq.scatter(end_threshold_freqs, end_threshold_amplitudes, color='red', marker='v', s=8, zorder=13)			

		#fig.show()

		return fig

	def DetectHarmonics(self):
		try:
			self.peak_freq_indices
		except:
			self.DetectFreqPeaks()

		#freq_max = self.freqs[self.peak_freq_indices[-1]] * 2 # Maximum frequency to check multiples of (set to Nyquist freq)
		freq_max = self.sampling_frequency / 2
		freq_displacement_means = []
		#print([self.freqs[i] for i in self.peak_freq_indices])
		for i, peak_index in enumerate(self.peak_freq_indices):
			fundamental_freq = self.freqs[peak_index]
			freq_multiples = np.arange(fundamental_freq*2, self.sampling_frequency / 2, fundamental_freq)

			if len(freq_multiples) > 0:
				freq_displacements = []
				for comparison_index in self.peak_freq_indices:
					if comparison_index != peak_index:
						comparison_freq = self.freqs[comparison_index]
						closest_freq_multiple_index = (np.abs(freq_multiples - comparison_freq)).argmin()
						closest_freq_multiple = freq_multiples[closest_freq_multiple_index]

						freq_displacements.append(abs(closest_freq_multiple - comparison_freq))

						#print("\t{} [{}] = {}".format(comparison_freq, closest_freq_multiple, freq_displacements[-1]))

				#print(freq_displacements)
				freq_displacement_means.append(np.average(freq_displacements))
				#print(freq_displacement_means)
				#print(peak_index)
				#print("{}Hz Peak Mean Displacement: {}".format(fundamental_freq, freq_displacement_means[i]))

		for peak_number in np.arange(len(freq_displacement_means)):
			fundamental_freq = self.freqs[self.peak_freq_indices[peak_number]]
			#print("{}Hz Peak Mean Displacement: {}\n".format(fundamental_freq, freq_displacement_means[peak_number]))
			for comparison_index in np.arange(len(freq_displacement_means)):
				if peak_number != comparison_index:
					comparison_freq = self.freqs[comparison_index]
					#print("\t{}: {}".format(comparison_freq, freq))

	def DetectFundamentalOld(self):
		try:
			self.peak_freq_indices
		except:
			self.DetectFreqPeaks()

		peak_pairs = zip(self.peak_freq_indices, self.peak_freq_indices[1:])
		peak_distances_with_outliers = []
		for peak_pair in peak_pairs:
			peak_distances_with_outliers.append(self.freqs[np.abs(peak_pair[0] - peak_pair[1])])

		peak_distance_mean_with_outliers = np.average(peak_distances_with_outliers)
		peak_distances = [d for d in peak_distances_with_outliers if np.abs(d - peak_distance_mean_with_outliers) / peak_distance_mean_with_outliers <= 0.5 or np.abs(d - peak_distance_mean_with_outliers) / peak_distance_mean_with_outliers >= 2]
		peak_distance_mean = np.average(peak_distances)

		# If more than 50% of the peaks were outliers:
		#print("{} vs {}".format(np.abs(len(peak_distances_with_outliers) - len(peak_distances)), 0.5 * len(peak_distances_with_outliers)))
		if np.abs(len(peak_distances_with_outliers) - len(peak_distances)) >= 0.5 * len(peak_distances_with_outliers):
			print("Peaks too ambiguous to determine a fundamental frequency")

		#print("with outliers: {}".format(peak_distances_with_outliers))
		#print("w/o outliers: {}".format(peak_distances))

		peak_freqs = [self.freqs[i] for i in self.peak_freq_indices]
		closest_peak_index = (np.abs(peak_freqs - peak_distance_mean)).argmin()
		self.fundamental_freq = peak_freqs[closest_peak_index]

		if np.abs(self.fundamental_freq - peak_distance_mean) / peak_distance_mean >= 0.25:
			print("No valid fundamental frequency peak found")

		#print("Closest peak: {}\nEstimated peak freq: {}".format(self.fundamental_freq, peak_distance_mean))

		return self.fundamental_freq

	def Autocorrelate(self, x):
	    autocorrelation = np.correlate(x, x, mode='full')
	    #print(autocorrelation.size)
	    result = autocorrelation[autocorrelation.size//2:].tolist()

	    for i in np.arange(1, len(result) // 10):

	    	print("{} -> {}".format(1 / self.times[i], result[i]))

	def DetectFundamental(self):
		try:
			self.peak_freq_indices
		except:
			self.DetectFreqPeaks()

		#max_testable_freq = self.sampling_frequency / 2
		max_testable_freq = self.freqs[self.peak_freq_indices[-1]] + 1

		peak_freqs = [self.freqs[f] for f in self.peak_freq_indices]
		#print("peak_freqs={}".format(peak_freqs))

		# Test 1: Multiples test;
		# Assume that all peaks are an integer multiple of f_f
		multiple_percentage_differences = []
		for fundamental_freq_index in self.peak_freq_indices:
			test_fundamental_freq = self.freqs[fundamental_freq_index]

			freq_multiples = np.arange(test_fundamental_freq*2, max_testable_freq, test_fundamental_freq)

			#print("Testing {}Hz as fundamental with multiples test...".format(test_fundamental_freq))
			#print(freq_multiples)			

			multiple_percentage_differences.append([])
			if len(freq_multiples) > 0:			
				for comparison_freq_index in [i for i in self.peak_freq_indices if i > fundamental_freq_index]:
					comparison_freq = self.freqs[comparison_freq_index]
					#print("\tComparing to {}Hz...".format(comparison_freq))

					closest_multiple_freq = freq_multiples[(np.abs(freq_multiples - comparison_freq)).argmin()]
					distance_to_multiple = closest_multiple_freq - comparison_freq
					multiple_percentage_differences[-1].append(distance_to_multiple / closest_multiple_freq * 100)

					#print("\t\tNearest multiple is {} (d={}; {}%)".format(closest_multiple_freq, distance_to_multiple, multiple_percentage_differences[-1][-1] * 100))


#		print('\nMultiples test results:')
#		multiples_p_values = []
#		for peak_number, data_set in enumerate(multiple_percentage_differences):
#			p = 1.0
#			if len(data_set) >= 2:
#				p = scipy.stats.ttest_1samp(data_set, 0)[1]
#
#			
#			#np.append(multiples_p_values, p)
#			multiples_p_values.append(p)


#		multiples_p_values_n = np.array(multiples_p_values, dtype=[('peak_number', int), ('p', float)])
#		multiples_p_values_filtered = multiples_p_values_n[multiples_p_values_n['p'] >= 0.0]
#		multiples_p_values_sorted = np.sort(multiples_p_values_filtered, order='p')
#		for peak_number, p in enumerate(multiples_p_values):
#			print("\t{}) {:.1f}Hz Peak: p = {:.2E}".format(peak_number+1, peak_freqs[peak_number], p))		
#		for i, (peak_number, p) in enumerate(multiples_p_values_sorted):
#			print("\t{}) {:.1f}Hz Peak: p = {:.2E}".format(i+1, peak_freqs[peak_number], p))


#		print("Results:")
#		for peak_number, percentage_difference in enumerate(multiple_percentage_differences):
#			if len(percentage_difference) > 0:
#				average_percent = "{:.3f}".format(np.average(percentage_difference) * 100)
#			else:
#				average_percent = "n/a"
#			print("\tPeak #{} ({:.1f}Hz): {}%".format(peak_number, self.freqs[self.peak_freq_indices[peak_number]], average_percent))

		#print("Mean Squared Errors (multiples test):")

		multiples_MSEs = []
		for peak_number, percentage_difference in enumerate(multiple_percentage_differences):
			if len(percentage_difference) > 0:
				MSE = MeanSquaredError(percentage_difference) * 100
				multiples_MSEs.append(MSE)
			else:
				MSE = "n/a"
				multiples_MSEs.append(-1)
			#print("\tPeak #{} ({:.1f}Hz): {}%".format(peak_number, self.freqs[self.peak_freq_indices[peak_number]], MSE))

		print("------")

		# Test 2: Distances test
		# Assume that all frequency multiples of f_f (up to freq of the final peak) have a corresponding peak
		distance_percentage_differences = []
		for fundamental_freq_index in self.peak_freq_indices:
			test_fundamental_freq = self.freqs[fundamental_freq_index]
			freq_multiples = np.arange(test_fundamental_freq*2, max_testable_freq, test_fundamental_freq)
			peak_freqs = [self.freqs[i] for i in self.peak_freq_indices]
			#print(peak_freqs)

			#print("Testing {}Hz as fundamental with distances test...".format(test_fundamental_freq))

			distance_percentage_differences.append([])
			for i, freq_multiple in enumerate(freq_multiples):
				#print("\tTesting {}Hz (multiple {})...".format(freq_multiple, i+1)) # +1 because 0-indexed

				#print("peak_freqs={}".format(peak_freqs))
				#print("peak_freqs(-)={}".format([f for f in peak_freqs if f!=test_fundamental_freq]))
				filtered_peak_freqs = [f for f in peak_freqs if f > test_fundamental_freq] # remove fundamental from the list so it's not comparing to itself

				if len(filtered_peak_freqs) > 0:
					nearest_peak_freq = filtered_peak_freqs[(np.abs(filtered_peak_freqs - freq_multiple)).argmin()]
					distance_to_peak = nearest_peak_freq - freq_multiple
					distance_percentage_differences[-1].append(distance_to_peak / nearest_peak_freq)

					#print("\t\t Nearest peak is {}Hz (d={}; {}%)".format(nearest_peak_freq, distance_to_peak, distance_percentage_differences[-1][-1] * 100))

#		print('\nDistances test results:')
#		distance_p_values = []
#		for peak_number, data_set in enumerate(distance_percentage_differences):
#			p = 1.0
#			if len(data_set) >= 2:
#				p = scipy.stats.ttest_1samp(data_set, 0)[1]
#			
#			#distance_p_values.append((peak_number, p))
#			distance_p_values.append(p)

		#print("Mean Squared Errors (distance test):")
		distances_MSEs = []
		for peak_number, percentage_difference in enumerate(distance_percentage_differences):
			if len(percentage_difference) > 0:
				MSE = MeanSquaredError(percentage_difference) * 100
				distances_MSEs.append(MSE)
			else:
				MSE = "n/a"
				distances_MSEs.append(-1)
			#print("\tPeak #{} ({:.1f}Hz): {}%".format(peak_number, self.freqs[self.peak_freq_indices[peak_number]], MSE))			


#		distance_p_values_n = np.array(distance_p_values, dtype=[('peak_number', int), ('p', float)])
#		distance_p_values_filtered = distance_p_values_n[distance_p_values_n['p'] >= 0.0]
#		distance_p_values_sorted = np.sort(distance_p_values_filtered, order='p')
		
#		for peak_number, p in enumerate(distance_p_values):
#			print("\t{}) {:.1f}Hz Peak: p = {:.2E}".format(peak_number+1, peak_freqs[peak_number], p))

#		#print("Results:")
#		for peak_number, percentage_difference in enumerate(distance_percentage_differences):
#			if len(percentage_difference) > 0:
#				average_percent = "{:.3f}".format(np.average(percentage_difference) * 100)
#			else:
#				average_percent = "n/a"
#			print("\tPeak #{} ({:.1f}Hz): {}%".format(peak_number, self.freqs[self.peak_freq_indices[peak_number]], average_percent))
#
#		combined_p_values = []
#		for peak_number in np.arange(0, len(peak_freqs)):
#			combined_p_values.append(multiples_p_values[peak_number] * distance_p_values[peak_number])
#
#		print("Combined p values...")
#		#combined_p_values_sorted = np.sort(combined_p_values)[::-1]
#		for i, combined_p_value in enumerate(combined_p_values):
#			print("\t{}Hz: p = {}".format(peak_freqs[i], combined_p_value))

		combined_MSEs = []
		for peak_number in np.arange(len(peak_freqs)):
			if multiples_MSEs[peak_number] > 0 and distances_MSEs[peak_number] > 0:
				combined_MSEs.append(pow(multiples_MSEs[peak_number] * distances_MSEs[peak_number], 0.5))
				#print("\t{}Hz: MSE_t = {}".format(peak_freqs[peak_number], combined_MSEs[peak_number]))
			else:
				combined_MSEs.append(-1)

		combined_MSEs_n = np.array(combined_MSEs)
		if len(combined_MSEs_n[combined_MSEs_n != -1]) > 0 and len(peak_freqs) > 0:
			#print(peak_freqs)
			#print(combined_MSEs_n)
			self.fundamental_freq = peak_freqs[combined_MSEs_n[combined_MSEs_n != -1].argmin()]
		else:
			self.fundamental_freq = -1

		return self.fundamental_freq			


def ParseAudioFileName(file_name):
	file_name_match = re.search('(\w*)_([a-zA-Z]{1,2})(\d)_', file_name)
	if file_name_match:
		instrument_name = file_name_match.group(1)
		note_name = file_name_match.group(2)
		octave_number = int(file_name_match.group(3))
		return instrument_name, note_name, octave_number
	else:
		print("File name regex match failed.")
		return "", "", ""

	#NoteToFreq(note_name, octave_number)

#def CheckFundamentalFrequencyWithFilename():






def RecordMic():
	sound = Waveform()
	sound.RecordFromMicrophone()
	figure = sound.GeneratePlots()

	frame = tk.Frame(notebook)
	notebook.add(frame, text="Recording")

	canvas = FigureCanvasTkAgg(figure, frame)
	canvas.draw()
	canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

	toolbar = NavigationToolbar2TkAgg(canvas, frame)
	toolbar.update()
	canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

#	fig, (ax_time, ax_freq) = plt.subplots(2, 1)
#
#	fig = Figure(figsize=(5,5), dpi=100)
#	waveform_plot = fig.add_subplot(2, 1, 1)
#	fft_plot = fig.add_subplot(2, 1, 2)

#	n = len(mic_ints) # number of samples
#	k = np.arange(n)
#	t = k / RATE # Creates discrete array of time values for our sampling frequency
#	T = n / RATE # Sample length in seconds
#	frq = k / T
#	frq = frq[range(n//2)]
	#frq = np.linspace(0.0, 1.0/(2.0*T), N/2)



#	global fft_raw_data
#	fft_raw_data = scipy.fftpack.fft(mic_ints)
#	fft_raw_data = fft_raw_data[range(n//2)]
#
#	print(str(len(t)))
#	print(str(len(mic_ints)))
#	waveform_plot.plot(t, mic_ints)
#	fft_plot.plot(frq, fft_raw_data)
#
#	canvas = FigureCanvasTkAgg(fig, master=root)
#	canvas.show()
#	canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=1)
#
#	toolbar = NavigationToolbar2TkAgg(canvas, root)
#	toolbar.update()
#	canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=1)

# Convert a list of bytes to a corresponding list of samples (as signed ints) of appropriate byte width.
def SampleWidthDataFromBytes(byte_list, sample_width):
	sample_width_lists = byte_list.reshape(-1, sample_width)

	sample_width_bytes = [bytes(e) for e in sample_width_lists]
	sample_width_ints = [int.from_bytes(e, byteorder='little', signed=True) for e in sample_width_bytes]

	return sample_width_ints
	
def AverageSTFT(data, to_print=False):
	data_sum = np.sum(data, 1)
	data_average = np.divide(data_sum, len(data))
	data_magnitude = np.absolute(data_average)

	if to_print:
		print("data_sum:{}".format(data_sum))
		print("data_average:{}".format(data_average))
		print("data_magnitude:{}".format(data_magnitude))

	return data_magnitude

def MeanSquaredError(data):
	data_squared = np.square(data)
	MSE = np.sum(data_squared) / len(data)

	return MSE


def OpenWAVFile(file_path = None):
	sound = Waveform()

	if not file_path:
		file_path = filedialog.askopenfilename()

	sound.LoadFromFile(file_path)

	frame = tk.Frame(notebook)
	file_name = os.path.basename(file_path)
	notebook.add(frame, text=file_name)

	fig, (ax_time, ax_freq) = plt.subplots(2, 1)

	#sound.Autocorrelate(sound.time_samples)
	#sound.DetectHarmonics2()

#	instrument_name, note_name, octave_number = ParseAudioFileName(file_name)
#	print("file name data:")
#	print("\tinstrument: {}".format(instrument_name))
#	print("\tnote: {}{}".format(note_name, octave_number))
#
#	actual_fundamental = NoteToFreq(note_name, octave_number)
#	detected_fundamental = sound.DetectFundamental()
#	print("\n\tactual fundamental: {}Hz".format(actual_fundamental))
#	print("\tdetected_fundamental: {}Hz".format(detected_fundamental))
#	print()

	figure = sound.GeneratePlots(True)

	#notebook.pack(side="top", fill="both", expand=True)


	canvas = FigureCanvasTkAgg(figure, frame)
	canvas.draw()
	canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

	toolbar = NavigationToolbar2TkAgg(canvas, frame)
	toolbar.update()
	canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

	plt.close("all")

def FundamentalFrequencyTest(file_path = None):
	sound = Waveform()

	if not file_path:
		file_path = filedialog.askopenfilename()

	sound.LoadFromFile(file_path)

	#frame = tk.Frame(notebook)
	#file_name = os.path.basename(file_path)
	#notebook.add(frame, text=file_name)

	#fig, (ax_time, ax_freq) = plt.subplots(2, 1)

	#sound.DetectHarmonics2(

	file_name = os.path.basename(file_path)
	instrument_name, note_name, octave_number = ParseAudioFileName(file_name)
	#print("file name data:")
	print("\tinstrument: {}".format(instrument_name))
	print("\tnote: {}{}".format(note_name, octave_number))

	actual_fundamental = NoteToFreq(note_name, octave_number)
	detected_fundamental = sound.DetectFundamental()
	print("\n\tactual fundamental: {}Hz".format(actual_fundamental))
	print("\tdetected_fundamental: {}Hz".format(detected_fundamental))
	percentage_difference = np.abs(actual_fundamental - detected_fundamental) / actual_fundamental * 100
	print("\tdifference: {:.2f}%".format(percentage_difference))

	del sound

	return percentage_difference

def AnalyzeFolder():
	folder_path = filedialog.askdirectory()

	for file_name in listdir(folder_path):
		file_path = folder_path + "/" + file_name
		print("Analyzing {}...".format(file_path))

		FundamentalFrequencyTest(file_path)



def ExportCSV():
	csv_filename = filedialog.asksaveasfilename(filetypes=[("Comma-separated values", 'csv')], defaultextension='csv')
	with open(csv_filename, 'wt') as csv_file:
		global fft_raw_data
		for e in fft_raw_data:
			csv_file.write(str(e))
			csv_file.write(',\n')

menubar = tk.Menu(root)
filemenu = tk.Menu(menubar, tearoff=0)
#filemenu.add_command(label="Open...", command=OpenWAVFile, underline=0)
filemenu.add_command(label="Open...", command=OpenWAVFile, underline=0)
filemenu.add_command(label="Analyze file", command=FundamentalFrequencyTest, underline=0)
filemenu.add_command(label="List files...", command=AnalyzeFolder, underline=0)
filemenu.add_command(label="Record", command=RecordMic, underline=0)
filemenu.add_command(label="Post memory", command=tracker.print_diff, underline=0)
filemenu.add_command(label="Quit", command=root.quit, underline=0)
menubar.add_cascade(label="File", menu=filemenu, underline=0)
root.config(menu=menubar)

if len(sys.argv) == 2:
	OpenWAVFile(sys.argv[1])

#Button(root, text="Quit", command=root.quit).pack()

root.mainloop()
#plt.close("all")