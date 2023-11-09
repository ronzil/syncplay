import wave
import time
import sys
import numpy as np
import pyaudio




#### CONSTANTS

# start the audio at the next round time in seconds. A value of 10 means that if now is 14:23:24, start at 14:23:30
START_AT_ROUND = 10

#### internal use globals. No need to change
wavi = 0 # index into the wav audio_data
stream_time_start = 0 # when in stream time should we start playing
sample_rate = 0 # output sample rate 
_chunk = [] #output buffer
_delaycount = 0 #delay counter
_skipcount = 0 # skip counter
#####

# add a delay to the output. param is in seconds in floating point
def add_delay(delta_s):
    global _delaycount
    _delaycount += round(delta_s * sample_rate)

# skip the sound by delay_s in seconds. If positive sound skips samples (forward in time) if negative sound repeats samples (backwards in time)
def add_skip(delta_s):
    global _skipcount
    _skipcount += round(delta_s * sample_rate)

# this is the main callback function that is called by the audio card to request samples
def callback(in_data, frame_count, time_info, status):
    # make sure the request frame_count is the expected size
    bufsize = len(_chunk)
    assert(bufsize == frame_count) # should be like this always
    
    # if this is the first call to callback. Calcuate how many samples we should delay to start at the right time
    global stream_time_start    
    if stream_time_start>0:
        # this is the time (in stream time) when the first sample will be played by the sound card
        output_time = time_info['output_buffer_dac_time']
        # the delay needed to start at the requested time
        delay_time = stream_time_start - output_time
        # add that much delay
        add_delay(delay_time)
        # remove the flag
        stream_time_start = 0
        
    
    global wavi
    global _delaycount
    global _skipcount
    # fill the audio buffer to send to the card
    # normally its just the next samples from audio_data cyclically
    # also allow adding delay and skipping
    for i in range(bufsize):
        # set the next sample
        _chunk[i] = audio_data[wavi]

        # if we need to introduce a delay, just continue the loop without incrementing wavi
        if _delaycount>0:
            _delaycount -= 1
            continue

        
        # if skip requested move wavi forward or backward
        if _skipcount != 0:
            wavi += _skipcount
            _skipcount = 0
            
        # increment the pointer in the sound buffer cyclically
        wavi += 1
        wavi %= len(audio_data)
   
    return (_chunk, pyaudio.paContinue)    



####################################
# Program starts here

# Get the wav file as a param
if len(sys.argv) < 2:
    print(f'Plays a wave file. Usage: {sys.argv[0]} filename.wav')
    sys.exit(-1)

filename = sys.argv[1]
print("Loading " + filename)
# Get the wav file into a buffer
wf = wave.open(filename, 'rb')
data = wf.readframes(wf.getnframes())
wf.close()


# Get the dtype according to the sample width of the WAV file
dtype_map = {
    1: np.uint8,    # 8-bit PCM
    2: np.int16,    # 16-bit PCM
    4: np.int32,    # 32-bit PCM
}
audio_dtype = dtype_map.get(wf.getsampwidth(), np.int16)  # Default to int16 if unsure

# save the audio_data that will be played
audio_data = np.frombuffer(data, dtype=audio_dtype)

# save sample rate
sample_rate = wf.getframerate()

print("File length: %f seconds and %d samples." % (len(audio_data)/sample_rate, len(audio_data)))
print("sample rate %d, channels %d, sample width %d" % (sample_rate, wf.getnchannels(), wf.getsampwidth()))



## Make a buffer for sending to the sound card
BUFSIZE = 1024 # size doesn't matter...
_chunk = np.zeros(BUFSIZE, dtype=audio_dtype)

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open an audio output stream using the callback function
stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                channels=wf.getnchannels(),
                rate=wf.getframerate(),
                output=True,
                start=False,
                frames_per_buffer=BUFSIZE,
                stream_callback=callback)

## Calculate when the stream should start
now = time.time()
time_to_start = now + (START_AT_ROUND - now % START_AT_ROUND)
print("Starting to play at " + time.ctime(time_to_start))

# get the offset between stream time and clock time
stream_time_offset = now - stream.get_time() # the time difference between stream time and clock time
# convert time_to_start from clock time to stream time 
stream_time_start = time_to_start - stream_time_offset


# Start the stream
stream.start_stream()

while stream.is_active():
    time.sleep(1)
    offset = time.time() - stream.get_time() # the time difference between stream time and clock time
    if abs(offset- stream_time_offset)>0.002:
        delta = offset - stream_time_offset
        print("Adjusting stream by %f miliseconds" % (delta*1000))
        add_skip(delta)
        stream_time_offset = offset
        

# Stop and close the stream
stream.stop_stream()
stream.close()

# Close PyAudio
p.terminate()
