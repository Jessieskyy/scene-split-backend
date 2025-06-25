from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import tempfile
import zipfile
import logging
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_subclip

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

logging.basicConfig(level=logging.INFO)

detected_scenes = []
video_path = None

@app.route("/")
def index():
    return "Scene Split Backend is running!"

@app.route("/detect", methods=["POST"])
def detect():
    global detected_scenes, video_path

    if 'video' not in request.files:
        app.logger.error("No video part in request.files")
        return jsonify({"error": "No video uploaded"}), 400

    file = request.files['video']
    if file.filename == '':
        app.logger.error("Empty filename uploaded")
        return jsonify({"error": "No video selected"}), 400

    temp_dir = tempfile.mkdtemp()
    video_path = os.path.join(temp_dir, file.filename)
    file.save(video_path)

    app.logger.info(f"Starting scene detection for file: {file.filename}")

    try:
        video_manager = VideoManager([video_path])
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=30.0))
        video_manager.set_downscale_factor()
        video_manager.start()
        scene_manager.detect_scenes(frame_source=video_manager)
        scenes = scene_manager.get_scene_list()

        detected_scenes = [(s[0].get_seconds(), s[1].get_seconds()) for s in scenes]
        app.logger.info(f"Scene detection completed: {len(scenes)} scenes found")

        return jsonify([{"start": f"{s[0]:.2f}", "end": f"{s[1]:.2f}"} for s in detected_scenes])

    except Exception as e:
        app.logger.error(f"Error during scene detection: {e}")
        return jsonify({"error": "Failed to process video."}), 500


@app.route("/export", methods=["POST"])
def export():
    global detected_scenes, video_path

    indices = request.json.get('indices')
    if not indices or not isinstance(indices, list):
        return jsonify({"error": "Invalid or missing 'indices'"}), 400

    zip_path = os.path.join(tempfile.gettempdir(), "scenes_export.zip")
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for i in indices:
            if i < 0 or i >= len(detected_scenes):
                continue
            start, end = detected_scenes[i]
            clip_path = os.path.join(tempfile.gettempdir(), f"scene_{i+1}.mp4")
            ffmpeg_extract_subclip(video_path, start, end, targetname=clip_path)
            zipf.write(clip_path, arcname=f"scene_{i+1}.mp4")

    return send_file(zip_path, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
