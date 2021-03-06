from atlasbuggy.cameras.picamera import PiCamera


class NaborisCam(PiCamera):
    def __init__(self, logger=None, video_recorder=None, enabled=True):
        super(NaborisCam, self).__init__(enabled, logger=logger, video_recorder=video_recorder)

    def init_cam(self, cam):
        cam.resolution = (cam.resolution[0] // 2, cam.resolution[1] // 2)
        cam.framerate = 30
        cam.hflip = True
        cam.vflip = True
