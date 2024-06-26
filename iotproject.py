import argparse
import warnings
import datetime
import imutils
import json
import numpy as np
import os
import time
import cv2

import board
import adafruit_mlx90614
import RPi.GPIO as gpio
import picamera
import time

import smtplib
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email import encoders
from email.mime.image import MIMEImage
from picamera import PiCamera
from smbus import SMBus

from googleapiclient.http import MediaFileUpload
from Google import Create_Service
CLIENT_SECRET_FILE = "client_secret_447267219151-vvj5o6lv8imfspqk2jdohc1scuqgiehe.apps.googleusercontent.com.json"
API_NAME = "drive"
API_VERSION = "v3"
SCOPES = ['https://www.googleapis.com/auth/drive']
service = Create_Service(CLIENT_SECRET_FILE, API_NAME, API_VERSION, SCOPES)
folder_id = '1tRkdWjVlWJETILV67MMRD3oS7euxpSxO'
mime_types = 'video/x-msvideo'

i2c = board.I2C()
mlx = adafruit_mlx90614.MLX90614(i2c)

 
fromaddr = "rathodricky29@gmail.com"    # change the email address accordingly
toaddr = "milindrrampure@gmail.com"
 
mail = MIMEMultipart()
 
mail['From'] = fromaddr
mail['To'] = toaddr
mail['Subject'] = "Temperature value exceed alert"
body = "Please find the attached image"
maill = MIMEMultipart()
maill['From'] = fromaddr
maill['To'] = toaddr
maill['Subject'] = "Room Occupied"
bodyy = "Check the drive folder for Video: https://drive.google.com/drive/folders/1tRkdWjVlWJETILV67MMRD3oS7euxpSxO?usp=sharing"
 
data=""
def sendMail(data):
    mail.attach(MIMEText(body, 'plain'))
    print (data)
    dat='%s.jpg'%data
    print (data)
    attachment = open(dat, 'rb')
    image=MIMEImage(attachment.read())
    attachment.close()
    mail.attach(image)
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(fromaddr, "MilindIsGreat@29")
    text = mail.as_string()
    server.sendmail(fromaddr, toaddr, text)
    server.quit()
    
def sendAlert():
    maill.attach(MIMEText(bodyy, 'plain'))
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(fromaddr, "MilindIsGreat@29")
    text = maill.as_string()
    server.sendmail(fromaddr, toaddr, text)
    server.quit()    

print("[INFO] Kicking off script - " +
      datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S"))

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-c", "--conf", required=True,
                help="path to the JSON configuration file")
args = vars(ap.parse_args())

# filter warnings, load the configuration
warnings.filterwarnings("ignore")
conf = json.load(open(args["conf"]))

# initialize the camera and grab a reference to the raw camera capture
# if the video argument is None, then we are reading from webcam

camera = cv2.VideoCapture(1)
time.sleep(0.25)


# allow the camera to warmup, then initialize the average frame, last
# uploaded timestamp, and frame motion counter
print("[INFO] warming up...")
time.sleep(conf["camera_warmup_time"])
avg = None
lastUploaded = datetime.datetime.now()
motion_counter = 0
non_motion_timer = conf["nonMotionTimer"]
#fourcc = 0x00000020  # a little hacky, but works for now
fourcc = cv2.VideoWriter_fourcc(*'XVID')
writer = None
(h, w) = (None, None)
zeros = None
output = None
made_recording = False

# capture frames from the camera
while True:
    bus = SMBus(1)
    print ("Object Temperature:",mlx.object_temperature)
    temp= mlx.object_temperature
    bus.close()
    if temp>32:
        camerapi = PiCamera()
        data= time.strftime("%d_%b_%Y|%H:%M:%S")
        camerapi.start_preview()
        time.sleep(5)
        print (data)
        camerapi.capture('%s.jpg'%data)
        camerapi.stop_preview()
        time.sleep(1)
        camerapi.close()
        sendMail(data)
        time.sleep(0.1)
    else:
        time.sleep(0.05)
    # grab the raw NumPy array representing the image and initialize
    # the timestamp and occupied/unoccupied text
    (grabbed, frame) = camera.read()

    timestamp = datetime.datetime.now()
    motion_detected = False

    # if the frame could not be grabbed, then we have reached the end
    # of the video
    if not grabbed:
        print("[INFO] Frame couldn't be grabbed. Breaking - " +
              datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S"))
        break

    # resize the frame, convert it to grayscale, and blur it
    frame = imutils.resize(frame, width=conf["resizeWidth"])
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    # if the average frame is None, initialize it
    if avg is None:
        print("[INFO] starting background model...")
        avg = gray.copy().astype("float")
        # frame.truncate(0)
        continue

    # accumulate the weighted average between the current frame and
    # previous frames, then compute the difference between the current
    # frame and running average
    cv2.accumulateWeighted(gray, avg, 0.5)
    frameDelta = cv2.absdiff(gray, cv2.convertScaleAbs(avg))

    # threshold the delta image, dilate the thresholded image to fill
    # in holes, then find contours on thresholded image
    thresh = cv2.threshold(frameDelta, conf["delta_thresh"], 255,
                           cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    (_, cnts, _) = cv2.findContours(thresh.copy(),
                                    cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # loop over the contours
    for c in cnts:
        # if the contour is too small, ignore it
        if cv2.contourArea(c) < conf["min_area"]:
            continue

        # compute the bounding box for the contour, draw it on the frame,
        # and update the text
        (x, y, w1, h1) = cv2.boundingRect(c)
        cv2.rectangle(frame, (x, y), (x + w1, y + h1), (0, 255, 0), 2)
        motion_detected = True

    fps = int(round(camera.get(cv2.CAP_PROP_FPS)))
    record_fps = 10
    ts = timestamp.strftime("%Y-%m-%d_%H_%M_%S")
    time_and_fps = ts + " - fps: " + str(fps)

    # draw the text and timestamp on the frame
    cv2.putText(frame, "Motion Detected: {}".format(motion_detected), (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    cv2.putText(frame, time_and_fps, (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.35, (0, 0, 255), 1)

    # Check if writer is None TODO: make path configurable
    if writer is None:
        filename = datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")
        file_path = (conf["userDir"] + "/{filename}.avi")
        file_path = file_path.format(filename=filename)
        file_names = (datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S") + '.avi')
        #print("{filename}.avi")
        (h2, w2) = frame.shape[:2]
        writer = cv2.VideoWriter(file_path, fourcc, record_fps, (w2, h2), True)
        zeros = np.zeros((h2, w2), dtype="uint8")

    def record_video():
        # construct the final output frame, storing the original frame
        output = np.zeros((h2, w2, 3), dtype="uint8")
        output[0:h2, 0:w2] = frame

        # write the output frame to file
        writer.write(output)
        # print("[DEBUG] Recording....")

    if motion_detected:

        # increment the motion counter
        motion_counter += 1

        # check to see if the number of frames with motion is high enough
        if motion_counter >= conf["min_motion_frames"]:
            if conf["create_image"]:
                # create image TODO: make path configurable
                image_path = (conf["userDir"] + "/{filename}.jpg").format(filename=filename)
                cv2.imwrite(image_path, frame)

            record_video()

            made_recording = True
            non_motion_timer = conf["nonMotionTimer"]

    # If there is no motion, continue recording until timer reaches 0
    # Else clean everything up
    else:  # TODO: implement a max recording time
        # print("[DEBUG] no motion")
        if made_recording is True and non_motion_timer > 0:
            non_motion_timer -= 1
            # print("[DEBUG] first else and timer: " + str(non_motion_timer))
            record_video()
            if non_motion_timer == 0:
                file_metadata = {
                'name': file_names,
                'parents': [folder_id]
                }

                media = MediaFileUpload('/home/pi/iotproject/{0}'.format(file_names),mimetype = mime_types)
                service.files().create(
                body = file_metadata,
                media_body = media,
                fields = 'id'
                ).execute()
                print("uploaded")
                sendAlert()
        else:
            # print("[DEBUG] hit else")
            motion_counter = 0
            if writer is not None:
                # print("[DEBUG] hit if 1")
                writer.release()
                writer = None
            if made_recording is False:
                # print("[DEBUG] hit if 2")
                os.remove(file_path)
            made_recording = False
            non_motion_timer = conf["nonMotionTimer"]

    # check to see if the frames should be displayed to screen
    if conf["show_video"]:
        cv2.imshow("Security Feed", frame)
        key = cv2.waitKey(1) & 0xFF

        # if the `q` key is pressed, break from the loop
        if key == ord("q"):
            break

# cleanup the camera and close any open windows
print("[INFO] cleaning up...")
camera.release()
cv2.destroyAllWindows()