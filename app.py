import os
import uuid
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
from moviepy.editor import VideoFileClip
from PIL import Image

# Configuration
UPLOAD_FOLDER = 'uploads'
THUMBNAIL_FOLDER = 'thumbnails'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

# Flask app setup
app = Flask(__name__)
CORS(app)


# --- Scene Detection ---
def detect_scenes(video_path, threshold=15.0):  # Lowered threshold for more sensitivity
    print(f"🎯 Detecting scenes in {video_path} with threshold {threshold}")

    video_manager = VideoManager([video_path])
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold))

    video_manager.set_downscale_factor()
    video_manager.start()
    scene_manager.detect_scenes(frame_source=video_manager)
    scene_list = scene_manager.get_scene_list()

    print(f"📽️ Detected {len(scene_list)} scenes")
    for i, (start, end) in enumerate(scene_list):
        print(f"  Scene {i + 1}: {start.get_seconds():.2f}s → {end.get_seconds():.2f}s")

    scenes = []
    for start, end in scene_list:
        scenes.append({
            'start': start.get_seconds(),
            'end': end.get_seconds()
        })

    return scenes


# --- Thumbnail Generator ---
def generate_thumbnail(video_path, time_in_seconds, scene_id):
    try:
        clip = VideoFileClip(video_path)
        frame = clip.get_frame(time_in_seconds)
        img = Image.fromarray(frame)
        thumb_path = os.path.join(THUMBNAIL_FOLDER, f'{scene_id}.jpg')
        img.save(thumb_path)
        clip.close()
        return thumb_path
    except Exception as e:
        print(f"❌ Thumbnail error at {time_in_seconds}s: {e}")
        return None


# --- Upload + Detect API ---
@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    file = request.files['video']
    if not file.filename.endswith(('.mp4', '.mov', '.mkv', '.avi')):
        return jsonify({'error': 'Unsupported file format'}), 400

    filename = f"{uuid.uuid4().hex}.mp4"
    video_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(video_path)
    print(f"📥 Uploaded: {filename}")

    # Step 1: Detect scenes
    scenes = detect_scenes(video_path)

    # Step 2: Generate thumbnails
    thumbnails = []
    for i, scene in enumerate(scenes):
        start = scene['start']
        scene_id = f"{filename}_{i}"
        thumb_path = generate_thumbnail(video_path, start + 0.1, scene_id)
        if thumb_path:
            thumbnails.append({
                'scene': i,
                'start': start,
                'end': scene['end'],
                'thumbnail_url': f'/thumbnail/{scene_id}.jpg'
            })

    return jsonify({
        'video': filename,
        'scenes': thumbnails
    })


# --- Serve Thumbnail ---
@app.route('/thumbnail/<thumb_filename>')
def serve_thumbnail(thumb_filename):
    thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_filename)
    if os.path.exists(thumb_path):
        return send_file(thumb_path, mimetype='image/jpeg')
    else:
        return jsonify({'error': 'Thumbnail not found'}), 404


# --- Health Check ---
@app.route('/status')
def status():
    return jsonify({'status': '✅ Server is running'})


# --- Main Entry Point ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
