import cv2
from atlasbuggy import get_platform
from atlasbuggy.cameras import VideoStream
from atlasbuggy.files import default_video_name, default_log_dir_name


class CvVideoRecorder(VideoStream):
    def __init__(self, file_name=None, directory=None, enabled=True, debug=False):
        file_name, directory = self.format_path_as_time(
            file_name, directory, default_video_name, default_log_dir_name
        )

        super(CvVideoRecorder, self).__init__(file_name, directory, ['mp4', 'avi'], enabled, debug)
        self.width = None
        self.height = None
        self.video_writer = None
        self.fourcc = None
        self.frame_buffer = []
        self.opened = False

    def start_recording(self, capture):
        if self.enabled:
            self.make_dir()
            self.capture = capture
            self.width = capture.width
            self.height = capture.height

            if self.file_name.endswith('avi'):
                codec = 'MJPG'
            elif self.file_name.endswith('mp4'):
                if get_platform() == 'mac':
                    codec = 'MP4V'
                else:
                    # TODO: Figure out mp4 recording in linux
                    # codec = 'DIVX'
                    codec = 'MJPG'
                    self.file_name = self.file_name[:-3] + "avi"
                    self.full_path = self.full_path[:-3] + "avi"
            else:
                raise ValueError("Invalid file format")
            self.fourcc = cv2.VideoWriter_fourcc(*codec)
            self.video_writer = cv2.VideoWriter()

            self.is_recording = True

    def record(self, frame):
        if self.enabled:
            if self.opened:
                self._write(frame)
            else:
                if len(self.frame_buffer) >= 50:
                    self.debug_print("Writing video to: '%s'. FPS: %0.2f" % (self.full_path, self.capture.fps_avg), ignore_flag=True)
                    self.video_writer.open(self.full_path, self.fourcc, self.capture.fps_avg, (self.width, self.height), True)
                    while len(self.frame_buffer) > 0:
                        self._write(self.frame_buffer.pop(0))
                    self.opened = True
                else:
                    self.frame_buffer.append(frame)

    def _write(self, frame):
        if frame.shape[0:2] != (self.height, self.width):
            frame = cv2.resize(frame, (self.height, self.width))
        if len(frame.shape) == 2:
            self.video_writer.write(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
        else:
            self.video_writer.write(frame)

    def stop_recording(self):
        if self.enabled and self.is_recording:
            self.video_writer.release()
            self.is_recording = False
