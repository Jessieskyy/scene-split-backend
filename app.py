import os
import uuid
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
from moviepy.editor import VideoFileClip
from zipfile import ZipFile

UPLOAD_DIR = "uploads"
SCENE_DIR = "scenes"
THUMB_DIR = "thumbnails"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SCENE_DIR, exist_ok=True)
os.makedirs(THUMB_DIR, exist_ok=True)

app = Flask(__name__)
CORS(app)


def detect_scenes(video_path):
    print("🧠 Starting scene detection...")

    video_manager = VideoManager([video_path])
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=30.0))

    video_manager.set_downscale_factor()
    video_manager.start()

    scene_manager.detect_scenes(frame_source=video_manager)
    scene_list = scene_manager.get_scene_list()

    fps = video_manager.get_framerate()
    scenes = [(int(start.get_seconds()), int(end.get_seconds())) for start, end in scene_list]

    print(f"✅ Detected {len(scenes)} scenes.")
    return scenes, fps


def export_scene_clip(video_path, start, end, index):
    output_path = os.path.join(SCENE_DIR, f"scene_{index + 1}.mp4")
    clip = VideoFileClip(video_path).subclip(start, end)
    clip.write_videofile(output_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)
    return output_path


def generate_thumbnail(video_path, time, index):
    output_path = os.path.join(THUMB_DIR, f"thumb_{index + 1}.png")
    clip = VideoFileClip(video_path)
    frame = clip.get_frame(time)
    clip.save_frame(output_path, t=time)
    return output_path


@app.route("/", methods=["GET"])
def index():
    return "Scene Split Backend is running!"


@app.route("/detect", methods=["POST"])
def detect():
    file = request.files.get("video")
    if not file:
        return "No file provided", 400

    unique_id = str(uuid.uuid4())
    filename = f"{unique_id}_{file.filename}"
    video_path = os.path.join(UPLOAD_DIR, filename)
    file.save(video_path)

    print(f"🎥 Uploaded: {filename}")
    scenes, fps = detect_scenes(video_path)

    # Estimate total time (approx. 2.5s per scene segment)
    time_estimate = len(scenes) * 2.5
    print(f"⏱️ Estimated total export time: ~{int(time_estimate)} seconds")

    scene_data = []
    for i, (start, end) in enumerate(scenes):
        thumb_path = generate_thumbnail(video_path, start + 0.5, i)
        scene_data.append({
            "index": i,
            "start": start,
            "end": end,
            "thumbnail": f"/thumbnail/{os.path.basename(thumb_path)}"
        })

    # Store metadata for export
    request.environ["scene_data"] = (video_path, scenes)

    return jsonify(scene_data)


@app.route("/export", methods=["POST"])
def export():
    data = request.json
    indices = data.get("indices", [])
    file = request.files.get("video")
    video_path = request.args.get("video_path")  # Optional future use

    # Temporary hack: use last uploaded video (could be refactored to track per-session)
    last_video = sorted(os.listdir(UPLOAD_DIR))[-1]
    video_path = os.path.join(UPLOAD_DIR, last_video)

    scenes, _ = detect_scenes(video_path)

    selected_scenes = [scenes[i] for i in indices]
    zip_path = os.path.join(SCENE_DIR, "scenes.zip")

    with ZipFile(zip_path, "w") as zipf:
        for i, (start, end) in enumerate(selected_scenes):
            output_path = export_scene_clip(video_path, start, end, i)
            zipf.write(output_path, arcname=os.path.basename(output_path))

    return send_file(zip_path, as_attachment=True)


@app.route("/thumbnail/<filename>")
def get_thumbnail(filename):
    return send_file(os.path.join(THUMB_DIR, filename))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
