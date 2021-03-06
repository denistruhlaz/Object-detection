import cv2
import numpy as np
from pyzbar.pyzbar import decode as qrCodeDecode
import time
from dbr import *

#capture = cv2.VideoCapture('rtsp://live:Demo123!@192.168.103.117:554?subtype=0') #kada zelimo video
capture = cv2.VideoCapture(0) #kada zelimo video
writer = None
#capture = cv2.VideoCapture(0)  #kada zelimo live kameru
#capture = cv2.imread('nesto.jpg') #TODO za slike moram napravit
widthHeightTarget = 190
confThreshHold = 0.5
nmsThreshHold = 0.3 #sto je broj manji to ce threshhold biti agresivniji i imat cemo manji broj bboxova unutar bboxova

frame_width = int(capture.get(3))
frame_height = int(capture.get(4))

size = (frame_width, frame_height)

classesFile = 'model.data/custom.names'
classNames = []
with open(classesFile, 'rt') as f:
    classNames = f.read().rstrip('\n').split('\n')

modelConfiguration = 'model.data/yolov4-helmet.cfg'
modelWeights = 'model.data/yolov4-helmet-detection.weights'

colors = [tuple(255 * np.random.rand(3)) for i in range(5)]

net = cv2.dnn.readNetFromDarknet(modelConfiguration, modelWeights)
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV) #tu mozemo odabrat i CUDA ako imamo graficku i drivere isntalirane
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU) #isto tako mozemo i ovdje odabrati CUDA ako imamo graficku, graficka puno brze obraduje sliku nego CPU

reader = BarcodeReader()
reader.init_license("t0070fQAAAFalWFBT1Q+rIAdJI7q1JgdzrPoL4pA2w64jRwHSwwJ2sqqR/sRpFS0Yn5DDorqDeDbZ/Iury+7CCyOQ/LcJTxQbiQ==")

def decodeBarcodes(img):
    for barcode in qrCodeDecode(img):
        myData = barcode.data.decode('utf-8')
        points = np.array([barcode.polygon], np.int32)
        points = points.reshape((-1, 1, 2))  # pozicioniranje obruba oko barcoda
        cv2.polylines(img, [points], True, (0, 255, 106), 4)  # dodavanje pointova oko barcodova kada ih procita
        textPoints = barcode.rect  # ovo su pointovi za text kada procita barcode
        cv2.putText(img, myData, (textPoints[0], textPoints[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 217, 255), 2)

def decodeBarcodesUsingDynamsoft(img):
    color = (0, 0, 255)
    thickness = 2
    textResults = reader.decode_buffer(img)
    settings = reader.get_runtime_settings()
    settings.barcode_format_ids = EnumBarcodeFormat.BF_QR_CODE | EnumBarcodeFormat.BF_DATAMATRIX | EnumBarcodeFormat.BF_PDF417 | EnumBarcodeFormat.BF_AZTEC | EnumBarcodeFormat.BF_MICRO_QR
    reader.update_runtime_settings(settings)
    if (textResults is not None):
        for out in textResults:
            points = out.localization_result.localization_points
            cv2.line(img, points[0], points[1], color, thickness)
            cv2.line(img, points[1], points[2], color, thickness)
            cv2.line(img, points[2], points[3], color, thickness)
            cv2.line(img, points[3], points[0], color, thickness)
            cv2.putText(img, out.barcode_text,
                       (min([point[0] for point in points]), min([point[1] for point in points])),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, color, thickness)


#glavna funkcija koja trazi objekte na slici / video zapisu / live kameri
def findObjects(outputs, img):
    hT, wT, cT = img.shape #hT - height, wT- width, cT - channels
    bbox = [] #bounding box
    classIds = []
    confValue = [] #confidance value

    for output in outputs:
        for detection in output:
            scores = detection[5:] #zelimo uklonit prvih 5 elemenata
            classId = np.argmax(scores) #i naci index od max value-a u listi
            confidance = scores[classId]
            if confidance > confThreshHold:
                w, h = int(detection[2] * wT), int(detection[3] * hT) #ovo mnozimo zato sto je dobijemo rezultat u decimalnom obliku i onda taj rez castamo u int
                x, y = int((detection[0] * wT) - w / 2), int((detection[1] * hT) - h / 2) #zato sto su x i y zapravo centar objekta kojeg trazimo
                bbox.append([x, y, w, h])
                classIds.append(classId)
                confValue.append(float(confidance))

    indexs = cv2.dnn.NMSBoxes(bbox, confValue, confThreshHold, nmsThreshHold)
    #print(indexs)
    for color, i in zip(colors, indexs):
        i = i[0]
        box = bbox[i]
        x, y, w, h = box[0], box[1], box[2], box[3]
        #corner points x+w i y+h
        cv2.rectangle(img, (x, y), (x + w, y + h), color, 2)
        cv2.putText(img, f'{classNames[classIds[i]].upper()} {int(confValue[i] * 100)}%', (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        #decodeBarcodes(img) #funkcija za citanje barkodova ce se pozvati samo u slucaju ako ima uspjesnog pronalaska objekata koje trazimo

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
writer = cv2.VideoWriter('outputs/result.avi', fourcc, 20, size)
while True:
    success, img = capture.read()
    blob = cv2.dnn.blobFromImage(img, 1/255, (widthHeightTarget, widthHeightTarget), [0, 0, 0], 1, crop=False) #ovo ce sliku pretvorit u blob
    net.setInput(blob)
    startTime = time.time()

    layerNames = net.getLayerNames() #s ovim cemo dobiti imena svih nasih layera
    #print(layerNames)
    #print(net.getUnconnectedOutLayers()) #s ovim cemo dobiti index od layereveih outputa sa tri razlicite vrijednosti jer imamo 3 output layera od darkneta53
    #s toga sa svakog layera zelimo dobiti vrijednost
    outputNames = [layerNames[i[0]-1] for i in net.getUnconnectedOutLayers()] #kako pocinjemo od 0 tako moramo oduzet vrijednost indexa npr index 327 je zapravo 326
    #print(outputNames) #ovo ce nam dat imena koje je pronasao od svih nasim output layera kojih ima 3 iliti output names of our output layera

    #sada cemo poslati ovu sliku nasem networku i tako mozemo naci output od outputNamesa layera
    outputs = net.forward(outputNames)
    # print(len(outputs))
    # print(type(outputs))
    # print(type(outputs[0]))
    # print(outputs[0].shape) #ovaj output je zapravo lista od kojih je svaki element u listi numpy array
    # rezultat ovoga je matrix koji ima 300[0], 1200[1], 4800[2] redova i 8 razlicith stupaca
    # 300/1200/4800 je broj of bounding boxes , dok broj 8 znaci 1-center x, 2-center y, 3-w, 4-h, 5-confidance da se ono sto trazimo nalazi tamo, a ostale 3 vrijednosti su predictions probabilites ostalih klasa
    #print(outputs[0][0]) primjer outputa jednog elementa

    findObjects(outputs, img)
    decodeBarcodesUsingDynamsoft(img)
    #saveResult(img, capture)
    #ako nema outputs, foldera napravi ga
    if not os.path.exists('outputs'):
        os.mkdir('outputs')

    if success == True:
        writer.write(img)
        if cv2.waitKey(1) & 0xFF == ord('s'):
            break

    print('FPS {:.1f}'.format(1 / (time.time() - startTime)))

    cv2.imshow('Image', img)
    cv2.waitKey(1)

writer.release()
capture.release()