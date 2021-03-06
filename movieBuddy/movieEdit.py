from moviepy.editor import *
from tqdm import tqdm
import os
import matplotlib.pyplot as plt


# If the wav file uses stereo, there are 2 audio channels so we average the channels.
# Return the absolute value so all of the amplitudes are positive.
def get_abs_avg_amps(amp):
    if len(amp) == 1:
        return abs(amp)
    else:
        return abs((amp[0] + amp[1])/2)


def get_max_amps(amps, start, stop=None):
    return max(amps[start:stop])


# Look in the movieBuddy folder for a video and generate clip from that video.
def get_clip():
    files = [ line.strip('\n') for line in os.popen('ls').readlines() ]
    files.remove('finished')
    files.remove('movieEdit.py')
    files.remove('wavewriting.py')
    files.remove('Edit')
    file_name = files[0]
    clip = VideoFileClip(file_name)
    return clip, file_name


# Receives a moviepy VideoClip as input and returns the sound array.
def get_sound_array(clip, frames_per_second=44100):
    print('Generating sound array ...')
    sound_array = clip.audio.to_soundarray(fps=frames_per_second)
    return sound_array


# Returns a running average on frames using average of the previous last amount.
def running_avg(frames, last):
    def get_average_window(window):
        return sum(window) / len(window)
    
    from collections import deque

    window = deque(frames[:last])
    window_avg = get_average_window(window)
    avg = []

    for frame in tqdm(frames[last:],'Computing running average...'):
        avg.append( window_avg ) 
        window_avg -= window.popleft()/frames_per_second # fast compute of running avg.
        window.append(frame)
        window_avg += frame / frames_per_second # fast compute of running avg. 

    return avg


# Creates a matplotlib preview of the sound array for the user to determine a 1 sec. span of silence.
# Construct a running average.
def create_sound_preview(sound_array, frames, frames_per_second, preview = False):
    print('Generating sound preview...')

    if preview:
        preview_size = 60*frames_per_second if frames/frames_per_second > 60 else frames
    else:
        preview_size = frames

    amps_x = [i for i in range(preview_size)]
    amps_y = [get_abs_avg_amps(sound_array[i]) for i in range(preview_size)]

    run_avg = running_avg(amps_y, frames_per_second)
    run_avg = [run_avg[0] for _ in range(frames_per_second//2)] + run_avg + [run_avg[-1] for _ in range(frames_per_second//2)]

    xlabels = ['{}m{}s'.format(int(xamp/frames_per_second//60), int(xamp/frames_per_second%60)) for xamp in amps_x]
    plt.xticks(amps_x[::frames_per_second], xlabels[::frames_per_second],rotation=90)
    plt.plot(amps_x, amps_y)
    plt.plot(amps_x, run_avg, c='yellow')
    plt.show()

    return run_avg


# Scan a user defined span of the running average for the maxmm wav amplitude.
def get_sound_threshold(amps, frames_per_second, start, stop):
    start = list(map(int, start.strip('s').split('m')))
    start = start[0] * 60 + start[1]
    start *= frames_per_second

    stop = list(map(int, stop.strip('s').split('m')))
    stop = stop[0] * 60 + stop[1]
    stop *= frames_per_second

    rtn = max(amps[start:stop])
    print('The max amp in running avg from {} to {} is {}'.format(start, stop, rtn))
    return rtn


# Get a user defined window of time for the beginning and end of silence in the clip.
# Needs the time in XmYYs format.
def get_silence_times(sound_array, frames_per_second):
    silent_start = input('Silence begins at (_m__s): ')
    silent_end =   input('Silence ends at (_m__s):   ')
    sound_threshold = get_sound_threshold(sound_array, frames_per_second, silent_start, silent_end)
    return sound_threshold


# Scan the sound array sample by sample. If amp drops below the sound threshold for
# longer than the min_time_span_for_silence, this is a silence portion of the video
# that will be cutout later on. Amps_y is used for plotting the sound graph.
def get_silences(sound_array, run_avg, frames, sound_threshold, min_time_span_for_silence):

    # Create variables needed for scanning the sound array.
    silences = []
    silence = False
    start, stop = 0, 0
    buffer = frames_per_second * 0.1
    amps_x = [i for i in range(frames)]
    amps_y = [] # amps used for the sound graph.

    for i in tqdm(range(frames),'finding silences...'):
        this_sample = sound_array[i]
        try:
            avg_amp = run_avg[i]
        except IndexError:
            avg_amp = 0
        amps_y.append(get_abs_avg_amps(this_sample))

        if avg_amp <= sound_threshold:
            if not silence:
                silence = True
                start = i + buffer

        if avg_amp >= sound_threshold and silence:
            silence = False
            stop = i - buffer
            if stop - start > min_time_span_for_silence:
                start = min(start, frames)
                stop = max(stop, 0)
                silences.append((start, stop))

    return amps_x, amps_y, silences


# Generate a list of time tuples with starting and stopping times for the portions
# of the clip that we are going to keep (non silence frames).
def get_frames_to_keep(silences, preview=False):
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

    if preview:
        last = 60
    else:
        last = seconds
    sound_time = silence_times[-1][1], last
    sound_times.append(sound_time)

    return sound_times


# Generate one final preview showing the sections to keep underlined in green.
def final_preview(sound_times, frames_per_second, frames, amps_x, amps_y):
    sounds_x = []
    preview_size = 60 if frames/frames_per_second > 60 else frames/frames_per_second
    for sound_time in sound_times:
        start_frames, end_frames = int(sound_time[0]*frames_per_second), int(sound_time[1]*frames_per_second)
        if sound_time[0] <= preview_size >= sound_time[1]:
            [sounds_x.append(i) for i in range(start_frames, end_frames)]
        print('start:',round(sound_time[0],3),'\tstop:',round(sound_time[1],3))

    set_x = set(sounds_x)
    silence_x = [ i for i in range(preview_size*frames_per_second) if i not in set_x]
    sounds_y = [ -0.01 for _ in sounds_x ]
    silence_y = [-0.01 for _ in silence_x]

    plt.plot(amps_x[:len(sounds_x)], amps_y[:len(sounds_y)])
    plt.scatter(sounds_x, sounds_y, c='green',s=1)
    plt.scatter(silence_x, silence_y, c='red',s=1)
    xlabels = ['{}m{}s'.format(int(xamp/frames_per_second//60), int(xamp/frames_per_second%60)) for xamp in amps_x[:len(sounds_x)]]
    plt.xticks(amps_x[:len(sounds_x):frames_per_second], xlabels[::frames_per_second],rotation=90)
    plt.show()


# For each subclip containing sound, determine the max amp for the clip.
# Use the max amp of the subclip to scale the subclips volume later on.
def get_volume_scale_factor(sound_times, frames_per_second, amps_y):
    max_amps = [get_max_amps(amps_y, int(s[0]*frames_per_second), int(s[1]*frames_per_second)) for s in sound_times ]
    volume_scale_to = 0.45
    clip_volume_scales = [volume_scale_to/max_amp for max_amp in max_amps]
    return clip_volume_scales


# Generate subclip objects. Concatenate the edited subclips to form the final clip object.
def combine_subclips(seconds, sound_times, clip, clip_volume_scales=None, preview=False):
    print('Concatenating', len(sound_times), 'subclips ...')
    clips = []
    i = 0
    orig_time = 'Original Video: {}m{}s'.format(int(seconds/60), int(seconds%60))
    new_seconds = sum([time[1] - time[0] for time in sound_times])
    new_time = 'Edited Video: {}m{}s'.format(int(new_seconds/60), int(new_seconds%60))
    print(orig_time, new_time, sep='\n')

    if preview:
        max_time = 60 # second preview
    else:
        max_time = seconds
    for time in tqdm(sound_times):
        if time[0] <= max_time:
            curr_clip = clip.subclip(time[0], time[1])#.volumex( clip_volume_scales[i] )
            clips.append(curr_clip)
        i += 1

    return clips


# Write final clip object into a mp4 file.
def write_file(file_name, final_clip):
    # Create mp4 of the final clip object. Write the mp4 file in the finished folder.
    print('Making final clip ...')
    file_name = file_name.split('.')[0]
    final_clip.write_videofile('finished/'+file_name+'-edited.mp4',temp_audiofile="temp-audio.m4a", remove_temp = True, codec = "libx264", audio_codec="aac")


# Close any open clip objects before exiting the program.
def close_clip_objects(*clips):
    for clip in clips:
        if type(clip) == VideoClip or type(clip) == VideoFileClip:
            clip.close()
        else:
            for c in clip:
                c.close()
    print('\tFinished!')


if __name__ == '__main__':
    
    # the clip of the mp4 file to edit.
    clip, file_name = get_clip()

    # Generate the sound array object used to detect volume throughout clip.
    frames_per_second = 11000
    sound_array = get_sound_array(clip, frames_per_second)
    frames = len(sound_array)
    seconds = frames / frames_per_second

    # Make a preview of first minute of the sound array.
    run_avg = create_sound_preview(sound_array, frames, frames_per_second, preview=True)

    # Get the silence time from the user. Needs the time in XmYYs format.
    #sound_threshold = get_silence_times(sound_array, frames_per_second)
    sound_threshold = get_silence_times(run_avg, frames_per_second)
    
    # Get the amps_y for plotting the amps in the sound graph and silences are portions to cutout.
    min_time_span_for_silence = 0.2 * frames_per_second
    amps_x, amps_y, silences = get_silences(sound_array, run_avg, frames, sound_threshold, min_time_span_for_silence)

    # A list of the time tuples for portions of the clip containing meaningful audio.
    sound_times = get_frames_to_keep(silences, preview= True)

    # Final preview of the sound portion.
    final_preview(sound_times, frames_per_second, frames, amps_x, amps_y)

    #clip_volume_scales = get_volume_scale_factor() # Coming soon. . .

    # Make subclips and combine them.
    clips = combine_subclips(seconds, sound_times, clip, preview=True)
    final_clip = concatenate_videoclips(clips)
    
    # Create the mp4 in the finished directory.
    write_file(file_name, final_clip)

    # Close any open moviepy clip objects.
    close_clip_objects(final_clip, clips, clip)
