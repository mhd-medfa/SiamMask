import rospy
from sensor_msgs.msg import Image as ImageMsg
# from cv_bridge import CvBridge
import cv2
import os
import numpy as np
import ros_numpy

import glob
from test import *
import os,sys,inspect
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir)
from experiments.siammask_sharp.custom import Custom

parser = argparse.ArgumentParser(description='PyTorch Tracking Demo')

parser.add_argument('--resume', default='experiments/siammask_sharp/SiamMask_DAVIS.pth', type=str,
                    metavar='PATH',help='path to latest checkpoint (default: none)')
parser.add_argument('--config', dest='config', default='experiments/siammask_sharp/config_davis.json',
                    help='hyper-parameter of SiamMask in json format')
parser.add_argument('--base_path', default='../../data/tennis', help='datasets')
parser.add_argument('--cpu', action='store_true', help='cpu mode')
args = parser.parse_args()

class Nodo(object):
    def __init__(self):
        # Params
        self.image = None
        # self.br = CvBridge()
        # Node cycle rate (in Hz).
        self.loop_rate = rospy.Rate(0.05)

        # Publishers
        # self.pub = rospy.Publisher('imagetimer', Image,queue_size=10)

        # Subscribers
        rospy.Subscriber("/r200/rgb/image_raw",ImageMsg,self.callback)

    def callback(self, msg):
        # rospy.loginfo('Image received...')
        self.image = ros_numpy.numpify(msg)#self.br.imgmsg_to_cv2(msg)


    def frame_capture(self):
        # rospy.loginfo("Timing images")
        #rospy.spin()
        # while not rospy.is_shutdown():
        # rospy.loginfo('publishing image')
        # #br = CvBridge()
        # # if self.image is not None:
        # #     self.pub.publish(br.cv2_to_imgmsg(self.image))
        self.loop_rate.sleep()
        return self.image

if __name__ == '__main__':
     # Setup device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    torch.backends.cudnn.benchmark = True

    # Setup Model
    cfg = load_config(args)
    siammask = Custom(anchors=cfg['anchors'])
    if args.resume:
        assert isfile(args.resume), 'Please download {} first.'.format(args.resume)
        siammask = load_pretrain(siammask, args.resume)

    siammask.eval().to(device)
    
    rospy.init_node("siammaskimage", anonymous=True)
    my_node = Nodo()
    frame = my_node.frame_capture()
    
    # Select ROI
    cv2.namedWindow("SiamMask", cv2.WND_PROP_FULLSCREEN)
    # cv2.setWindowProperty("SiamMask", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    try:
        init_rect = cv2.selectROI('SiamMask', frame, False, False)
        x, y, w, h = init_rect
    except:
        
        exit()

    toc = 0
    f = 0
    while not rospy.is_shutdown():
        tic = cv2.getTickCount()
        # Capture the video frame
        # by frame
        frame = my_node.frame_capture()
        if f == 0:  # init
            f=1
            target_pos = np.array([x + w / 2, y + h / 2])
            target_sz = np.array([w, h])
            state = siamese_init(frame, target_pos, target_sz, siammask, cfg['hp'], device=device)  # init tracker
        elif f > 0:  # tracking
            state = siamese_track(state, frame, mask_enable=True, refine_enable=True, device=device)  # track
            location = state['ploygon'].flatten()
            mask = state['mask'] > state['p'].seg_thr

            frame[:, :, 2] = (mask > 0) * 255 + (mask == 0) * frame[:, :, 2]
            cv2.polylines(frame, [np.int0(location).reshape((-1, 1, 2))], True, (0, 255, 0), 3)
            cv2.imshow('SiamMask', frame)
            key = cv2.waitKey(0)
            if key > 0:
                break

        toc += cv2.getTickCount() - tic
    toc /= cv2.getTickFrequency()
    fps = f / toc
    print('SiamMask Time: {:02.1f}s Speed: {:3.1f}fps (with visulization!)'.format(toc, fps))

        