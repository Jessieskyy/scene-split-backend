from flask import Flask, request, jsonify, send_file
import os, tempfile, zipfile
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip

app = Flask(__name__)
detected_scenes = []
video_path = None

@app.route("/")
def home():
    return "Scene Split Backend is running!"

@app.route("/detect", methods=["POST"])
def detect():
    global detected_scenes, video_path
    file = request.files['video']
    temp_dir = tempfile.mkdtemp()
    video_path = os.path.join(temp_dir, file.filename)
    file.save(video_path)

    video_manager = VideoManager([video_path])
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=30.0))
    video_manager.set_downscale_factor()
    video_manager.start()
    scene_manager.detect_scenes(frame_source=video_manager)
    scenes = scene_manager.get_scene_list()
    detected_scenes = [(s[0].get_seconds(), s[1].get_seconds()) for s in scenes]
    return jsonify([{"start": f"{s[0]:.2f}", "end": f"{s[1]:.2f}"} for s in detected_scenes])

@app.route("/export", methods=["POST"])
def export():
    indices = request.json['indices']
    zip_path = os.path.join(tempfile.gettempdir(), "scenes_export.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for i in indices:
            start, end = detected_scenes[i]
            clip_path = os.path.join(tempfile.gettempdir(), f"scene_{i+1}.mp4")
            ffmpeg_extract_subclip(video_path, start, end, targetname=clip_path)
            zipf.write(clip_path, arcname=f"scene_{i+1}.mp4")
    return send_file(zip_path, as_attachment=True)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
