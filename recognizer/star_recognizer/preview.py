"""Native OpenCV debug window. Mirroring affects display only."""
CONNECTIONS = ((11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),
               (23,24),(23,25),(25,27),(27,29),(29,31),(24,26),(26,28),(28,30),(30,32))

def show(frame, sample, status, mirror, transport_status):
    import cv2
    image = frame.image.copy()
    h, w = image.shape[:2]
    for pose in sample.poses:
        for a,b in CONNECTIONS:
            if len(pose) > max(a,b) and min(pose[a].visibility,pose[b].visibility) >= 0.5:
                pa,pb=pose[a],pose[b]
                cv2.line(image,(round(pa.x*w),round(pa.y*h)),(round(pb.x*w),round(pb.y*h)),(80,220,130),2)
    if mirror:
        image=cv2.flip(image,1)
    lines = [f"{status['state']}  {status['action']}  {status['reason']}",
             f"generation {status['generation']}  {transport_status}",
             "Q / Esc: quit. Body left/right is independent of display mirroring."]
    for i,line in enumerate(lines):
        cv2.putText(image,line,(12,26+i*25),cv2.FONT_HERSHEY_SIMPLEX,0.48,(0,0,0),3,cv2.LINE_AA)
        cv2.putText(image,line,(12,26+i*25),cv2.FONT_HERSHEY_SIMPLEX,0.48,(245,245,245),1,cv2.LINE_AA)
    cv2.imshow("Star Pose - native debug preview",image)
    return cv2.waitKey(1) & 0xff not in (27,ord("q"),ord("Q"))
