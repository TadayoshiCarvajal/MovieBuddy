from moviepy.editor import *
import io
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import wave
from pydub import AudioSegment
import os
from time import sleep

def make_audio_files(file_name):
    from math import ceil
    
    main_audio = AudioFileClip(file_name)
    n_clips = ceil(main_audio.duration/30)
    print(n_clips)
    audio_subclips = []

    for i in range(n_clips):
        start = i * 30
        stop = min( (i+1) * 30, main_audio.duration )
        clip = main_audio.subclip(start, stop)
        audio_subclips.append(clip)
    
    audio_file_names = []
    i = 0
    for subclip in audio_subclips:
        ii = str(i).zfill(3)
        fname = 'audio_subclip'+ii+'.wav'
        audio_file_names.append(fname)
        print('Writing file:', fname,'...')
        subclip.write_audiofile(fname)
        i += 1
    return audio_file_names

def stereo_to_mono(audio_files):
    import os
    for old_file in audio_files:
        sound = AudioSegment.from_wav(old_file)
        sound = sound.set_channels(1)
        sound.export('mono_'+old_file, format="wav")
        os.system('rm '+old_file)

def transcribe_file(speech_file):
    """Transcribe the given audio file."""
    client = speech.SpeechClient()

    with io.open(speech_file, 'rb') as audio_file:
        content = audio_file.read()

    audio = types.RecognitionAudio(content=content)
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=44100,
        language_code='en-US',
        enable_word_time_offsets=True)

    response = client.recognize(config, audio)
    # Each result is for a consecutive portion of the audio. Iterate through
    # them to get the transcripts for the entire audio file.
    for result in response.results:

        alternative = result.alternatives[0]
        print(u'Transcript: {}'.format(alternative.transcript))
        print('Confidence: {}'.format(alternative.confidence))

        for word_info in alternative.words:
            word = word_info.word
            start_time = word_info.start_time
            end_time = word_info.end_time
            print('Word: {}{} start_time: {}(nanos: {}), end_time: {}(nanos: {})'.format(
                word,
                '_'*20,
                start_time.seconds + start_time.nanos * 1e-9,
                start_time.nanos,
                end_time.seconds + end_time.nanos * 1e-9,
                end_time.nanos))

def transcribe_file_punctuation(speech_file, offset):
    """Transcribe the given audio file."""
    from google.cloud import speech_v1p1beta1 as speech

    client = speech.SpeechClient()

    with io.open(speech_file, 'rb') as audio_file:
        content = audio_file.read()

    audio = speech.types.RecognitionAudio(content=content)
    config = speech.types.RecognitionConfig(
        encoding=speech.enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=44100,
        language_code='en-US',
        # Enable automatic punctuation
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True)

    response = client.recognize(config, audio)

    # Each result is for a consecutive portion of the audio. Iterate through
    # them to get the transcripts for the entire audio file.
    
    mode = 'w' if offset == 0 else 'a'
    
    for result in response.results:
        words = [] # What we return at the end.
        alternative = result.alternatives[0]
        print(u'Transcript: {}'.format(alternative.transcript))
        print('Confidence: {}'.format(alternative.confidence))
        write_to_script(alternative.transcript, mode)

        for word_info in alternative.words:
            word = word_info.word.strip(PUNCTUATION)
            start_time = word_info.start_time.seconds + (word_info.start_time.nanos * 1e-9) + offset
            end_time = word_info.end_time.seconds + (word_info.end_time.nanos * 1e-9) + offset
            words.append((word, start_time, end_time))
    return words

def write_to_script(transcript, mode):
    script_file = open('script.txt', mode)
    script_file.write('\t'+transcript)
    script_file.write('\n\t')
    script_file.close()

def read_from_script():
    script_file = open('script.txt', 'r')
    words_kept = script_file.read().split()
    script_file.close()
    return words_kept

def wait_for_revised_script():
    while True:
        input('\n\tMake your edits to script.txt. Save the file, close it, and \n\
        return to the console. IMPORTANT: YOU CAN ONLY DELETE WORDS, DO NOT \n\
        EDIT OR ADD NEW WORDS! SOME WORDS MIGHT BE INACCURATELY TRANSCRIBED. \n\
        PLEASE DO NOT CORRECT THEM IN THE TRANSCRIPT! When you are done, press \n\
        ENTER on the keyboard to continue...'.upper())
        words_kept = read_from_script()
        print('Revised Transcript: ', end='')
        print(' '.join(words_kept))
        query = input('Type Enter to continue or type R and press enter to revise the transcript:')
        if query.lower() != 'r':
            break
    return words_kept

def get_time_ranges(words, words_kept):
    words.reverse() # use words as a stack.
    time_ranges = []
    keeping = False # keeping this portion of the audio?
    print('words: {} words_kept: {}'.format(len(words), len(words_kept)))
    start, stop = None, None
    i = 0
    buffer = 0.1
    final_time = words[0][2]
    while i < len(words_kept):
        this_word = words_kept[i].strip(PUNCTUATION)
        test_word_data = words.pop()
        if test_word_data[0] == this_word:
            if not keeping:
                keeping = True
                start = max(test_word_data[1]-buffer,0) # Start is the start time of this word
            i += 1
        else:
            if keeping:
                keeping = False
                stop = min(test_word_data[1]+buffer, final_time) # Stop time is the start time of this word
                time_ranges.append( (start, stop) )
        
    if words and start is not None: # If we still have words in the words list, then they should be ignored.
        test_word_data = words.pop()
        stop = min(test_word_data[1]+buffer, final_time) # Stop time is the start time of this word
        time_ranges.append( (start, stop) )
    else:
        stop = test_word_data[2]
        time_ranges.append( (start, stop) )

    return time_ranges

def get_sub_clips(time_ranges, file_name):
    subclips = []
    orig_clip = VideoFileClip(file_name)

    for tr in time_ranges:
        clip = orig_clip.subclip(tr[0],tr[1])
        subclips.append(clip)
    return subclips

def create_final_clip(subclips):
    final_clip = concatenate_videoclips(subclips)
    final_clip.write_videofile('final-'+file_name,temp_audiofile="temp-audio.m4a", remove_temp = True, codec = "libx264", audio_codec="aac")
    
    # Close all
    final_clip.close()
    for clip in subclips:
        clip.close()

if __name__ == '__main__':
    
    PUNCTUATION = '.!-,'

    file_name = 'ep11fg-edited.mp4'

    # Generate and audio file and split audio up into multiple <=30 second long files.
    audio_files = make_audio_files(file_name) # a list of audio file names

    # Convert wav stereo files to mono:
    stereo_to_mono(audio_files)
    
    # Phase 1: Get the words and write the transcript to a txt file called script.txt
    words = []
    words_txt = open('words.txt', 'w')
    i = 0
    for audio_file in audio_files:
        offset = i * 30
        fname = 'mono_'+audio_file
        file_words = transcribe_file_punctuation(fname, offset) # words for this audio file
        for word in file_words:
            words.append(word)
            words_txt.write(str(word)+'\n')
        os.system('rm '+fname)
        i += 1
    
    sleep(3)

    # Phase 2: User modifies script.txt and presses enter. Read words in script 1 at a time.
    words_kept = wait_for_revised_script()

    # Phase #3: Get the time ranges that we are going to keep in the final clip.
    time_ranges = get_time_ranges(words, words_kept)
    
    # Phase #4: Cut the audio based on the time ranges
    subclips = get_sub_clips(time_ranges, file_name)

    # Phase #5: Concat the subclips and write.
    create_final_clip(subclips)

    words_txt.close()