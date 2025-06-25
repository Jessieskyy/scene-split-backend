from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os, tempfile, zipfile
from scenedetect import detect, ContentDetector
from moviepy.editor import VideoFileClip
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip

app = Flask(__name__)
CORS(app)

detected_scenes = []
video_path = None
scene_thumbnails = []

@app.route("/")
def home():
    return "Scene Split Backend is running!"

@app.route("/detect", methods=["POST"])
def detect_scenes():
    global detected_scenes, video_path, scene_thumbnails
    file = request.files['video']
    temp_dir = tempfile.mkdtemp()
    video_path = os.path.join(temp_dir, file.filename)
    file.save(video_path)

    # Scene Detection
    scene_list = detect(video_path, ContentDetector(threshold=30.0))
    detected_scenes = [(s[0].get_seconds(), s[1].get_seconds()) for s in scene_list]

    # Generate thumbnails
    clip = VideoFileClip(video_path)
    scene_thumbnails = []
    thumb_dir = os.path.join(temp_dir, "thumbs")
    os.makedirs(thumb_dir, exist_ok=True)
    for i, (start, end) in enumerate(detected_scenes):
        thumb_path = os.path.join(thumb_dir, f"thumb_{i}.jpg")
        mid_time = (start + end) / 2
        clip.save_frame(thumb_path, t=mid_time)
        scene_thumbnails.append(thumb_path)

    # Send scene ranges and temporary thumb URLs
    return jsonify([
        {
            "start": round(start, 2),
            "end": round(end, 2),
            "thumb": f"/thumbnail/{i}"
        }
        for i, (start, end) in enumerate(detected_scenes)
    ])

@app.route("/thumbnail/<int:index>")
def serve_thumb(index):
    if 0 <= index < len(scene_thumbnails):
        return send_file(scene_thumbnails[index], mimetype='image/jpeg')
    return "Thumbnail not found", 404

@app.route("/export", methods=["POST"])
def export_scenes():
    indices = request.json['indices']
    zip_path = os.path.join(tempfile.gettempdir(), "scenes_export.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for i in indices:
            start, end = detected_scenes[i]
            clip_path = os.path.join(tempfile.gettempdir(), f"scene_{i+1}.mp4")
            ffmpeg_extract_subclip(video_path, start, end, targetname=clip_path)
            zipf.write(clip_path, arcname=f"scene_{i+1}.mp4")
    return send_file(zip_path, as_attachment=True)
