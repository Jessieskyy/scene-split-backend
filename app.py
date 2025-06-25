import os
import uuid
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
from moviepy.editor import VideoFileClip
from zipfile import ZipFile

UPLOAD_FOLDER = "uploads"
THUMBNAIL_FOLDER = "thumbnails"
SCENE_FOLDER = "scenes"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
os.makedirs(SCENE_FOLDER, exist_ok=True)

app = Flask(__name__)
CORS(app)


def detect_scenes(video_path, threshold=30.0):
    video_manager = VideoManager([video_path])
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))

    video_manager.set_downscale_factor()
    video_manager.start()
    scene_manager.detect_scenes(frame_source=video_manager)
    scene_list = scene_manager.get_scene_list()

    scenes = []
    for start, end in scene_list:
        start_sec = start.get_seconds()
        end_sec = end.get_seconds()
        scenes.append({
            "start": start_sec,
            "end": end_sec
        })
    return scenes


def generate_thumbnail(video_path, time_in_seconds, scene_id):
    clip = VideoFileClip(video_path)
    # Extract frame and save as JPG thumbnail
    clip.save_frame(os.path.join(THUMBNAIL_FOLDER, f"{scene_id}.jpg"), t=time_in_seconds)
    clip.close()
    return f"/thumbnail/{scene_id}.jpg"


def export_scene_clip(video_path, start, end, index):
    output_path = os.path.join(SCENE_FOLDER, f"scene_{index + 1}.mp4")
    clip = VideoFileClip(video_path).subclip(start, end)
    clip.write_videofile(output_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)
    clip.close()
    return output_path


@app.route("/upload", methods=["POST"])
def upload_video():
    if "video" not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    file = request.files["video"]
    filename = f"{uuid.uuid4().hex}.mp4"
    video_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(video_path)

    # Detect scenes
    scenes = detect_scenes(video_path)

    # Generate thumbnails for each scene start + small offset
    scene_data = []
    for i, scene in enumerate(scenes):
        start = scene["start"]
        scene_id = f"{filename}_{i}"
        thumb_url = generate_thumbnail(video_path, start + 0.1, scene_id)
        scene_data.append({
            "scene": i,
            "start": start,
            "end": scene["end"],
            "thumbnail_url": thumb_url
        })

    return jsonify({
        "video": filename,
        "scenes": scene_data
    })


@app.route("/thumbnail/<thumb_filename>")
def serve_thumbnail(thumb_filename):
    thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_filename)
    if os.path.exists(thumb_path):
        return send_file(thumb_path, mimetype="image/jpeg")
    else:
        return jsonify({"error": "Thumbnail not found"}), 404


@app.route("/export", methods=["POST"])
def export_scenes():
    data = request.json
    indices = data.get("indices", [])
    video_filename = data.get("video")

    if not video_filename:
        return jsonify({"error": "Video filename not provided"}), 400

    video_path = os.path.join(UPLOAD_FOLDER, video_filename)
    if not os.path.exists(video_path):
        return jsonify({"error": "Video file not found"}), 404

    scenes = detect_scenes(video_path)
    selected_scenes = [scenes[i] for i in indices if i < len(scenes)]

    zip_path = os.path.join(SCENE_FOLDER, "scenes.zip")
    with ZipFile(zip_path, "w") as zipf:
        for i, scene in enumerate(selected_scenes):
            output_path = export_scene_clip(video_path, scene["start"], scene["end"], i)
            zipf.write(output_path, arcname=os.path.basename(output_path))

    return send_file(zip_path, as_attachment=True)


@app.route("/status")
def status():
    return jsonify({"status": "Server is up and running!"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
