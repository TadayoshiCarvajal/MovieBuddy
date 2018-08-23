from moviepy.editor import *
from tqdm import tqdm
import os
import matplotlib.pyplot as plt

def get_silence_theshold(amps, frames_per_second, start, stop):
    from numpy import amax as maxmm
    from numpy import abs as npabs
    start = list(map(int, start.strip('s').split('m')))
    start = start[0] * 60 + start[1]
    start *= frames_per_second

    stop = list(map(int, stop.strip('s').split('m')))
    stop = stop[0] * 60 + stop[1]
    stop *= frames_per_second

    rtn = maxmm( npabs(amps[start:stop,0]/2 + amps[start:stop,1]/2) )
    print('The max amp from {} to {} is {}'.format(start, stop, rtn))
    return rtn

def get_abs_avg_amps(amp):
    return abs((amp[0] + amp[1])/2)

def get_max_amps(amps, start, stop=None):
    return max(amps[start:stop])

# Look in the movieBuddy folder for a video and generate clip from that video.
files = [ line.strip('\n') for line in os.popen('ls').readlines() ]
files.remove('finished')
files.remove('movieEdit.py')
files.remove('wavewriting.py')
file_name = files[0]
clip = VideoFileClip(file_name)#.subclip(0,60)

# Generate the sound array object used to detect volume throughout clip.
print('Generating sound array ...')
frames_per_second = 11000
sound_array = clip.audio.to_soundarray(fps=frames_per_second)
frames = len(sound_array)
seconds = frames / frames_per_second

# Create variables needed for scanning the sound array.
print('Parsing sound array ...')
silences = []
silence = False
start, stop = 0, 0
silence_threshold = 0.5 * frames_per_second
buffer = frames_per_second * 0.1

print('Getting sound array preview...')
print('Find a starting and ending time frame in the preview where there is silence.')
amps_x = [i for i in range(frames//10)]
amps_y = [get_abs_avg_amps(sound_array[i]) for i in range(frames//10)]
xlabels = ['{}m{}s'.format(int(xamp/frames_per_second//60), int(xamp/frames_per_second%60)) for xamp in amps_x]
plt.xticks(amps_x[::frames_per_second], xlabels[::frames_per_second],rotation=90)
plt.plot(amps_x, amps_y)
plt.show()

silent_start = input('Silence begins at (_m__s): ')
silent_end =   input('Silence ends at (_m__s):   ')
sound_threshold = get_silence_theshold(sound_array, frames_per_second, silent_start, silent_end)

amps_y = [] # reset amps_y

for i in tqdm(range(frames//10)):
    # Scan the sound array sample by sample. If amp drops below the sound threshold for
    # longer than the silence_threshold, this is a silence portion of the video
    # that will be cutout later on.
    this_sample = sound_array[i]
    avg_amp = get_abs_avg_amps(this_sample)
    amps_y.append(avg_amp)

    if avg_amp <= sound_threshold:
        if not silence:
            silence = True
            start = i + buffer

    if avg_amp >= sound_threshold and silence:
        silence = False
        stop = i - buffer
        if stop - start > silence_threshold:
            start = min(start, frames)
            stop = max(stop, 0)
            silences.append((start, stop))

# Create a list of time tuples indicating starting and stopping times for silence portions.
silence_times = []
for s in silences:
    silence_times.append( (s[0]/frames_per_second, s[1]/frames_per_second) )

# Create a list of time tuples indicating starting and stopping times for sound.
sound_times = []
sound_time = 0.0, silence_times[0][0]
sound_times.append(sound_time)
for i in range(1, len(silence_times)):
    sound_time = silence_times[i-1][1], silence_times[i][0]
    sound_times.append(sound_time)
sound_time = silence_times[-1][1], seconds / 10
sound_times.append(sound_time)

sounds_x = []
for st in sound_times:
    start_frames, end_frames = int(st[0]*frames_per_second), int(frames_per_second * st[1])
    if end_frames <= frames // 10:
        [sounds_x.append(i) for i in range(start_frames, end_frames)]
    else:
        break
sounds_y = [ -0.01 for _ in sounds_x ]

for time in sound_times:
    print(time)
plt.plot(amps_x, amps_y)
plt.scatter(sounds_x, sounds_y, c='green',s=1)
xlabels = ['{}m{}s'.format(int(xamp/frames_per_second//60), int(xamp/frames_per_second%60)) for xamp in amps_x]
plt.xticks(amps_x[::frames_per_second], xlabels[::frames_per_second],rotation=90)
plt.show()

# For each subclip containing sound, determine the max amp for the clip.
# Use the max amp of the subclip to scale the subclips volume later on.
max_amps = [get_max_amps(amps_y, int(s[0]*frames_per_second), int(s[1]*frames_per_second)) for s in sound_times ]
volume_scale_to = 0.45
clip_volume_scales = [volume_scale_to/max_amp for max_amp in max_amps]

# Generate subclip objects and scale their volumes using clip_volume_scales[i]. 
# Concatenate the edited subclips to form the final clip object.
print('Concatenating', len(sound_times), 'subclips ...')
clips = []
i = 0
orig_time = 'Original Video: {}m{}s'.format(int(seconds//60), int(seconds%60))
new_seconds = sum([time[1] - time[0] for time in sound_times])
new_time = 'Edited Video: {}m{}s'.format(int(new_seconds//60), int(new_seconds%60))

print(orig_time, new_time, sep='\n')
for time in tqdm(sound_times):
    curr_clip = clip.subclip(time[0], time[1])#.volumex( clip_volume_scales[i] )
    clips.append(curr_clip)
    i += 1
final_clip = concatenate_videoclips(clips)

final_clip_p = final_clip.subclip(0, final_clip.duration).resize(width = 240)
'''
while True:
    final_clip_p.preview()
    q = input('Type anything to continue, or type C to cancel')
    if q.lower() == 'c':
        print('Exiting...')
        exit()

'''

# Create mp4 of the final clip object. Write the mp4 file in the finished folder.
print('Making final clip ...')
file_name = file_name.split('.')[0]
final_clip.write_videofile('finished/'+file_name+'-edited.mp4',temp_audiofile="temp-audio.m4a", remove_temp = True, codec = "libx264", audio_codec="aac")

final_clip.close()
for c in clips:
    c.close()
clip.close()
print('\tFinished!')