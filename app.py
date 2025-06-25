import os
import uuid
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from scenedetect import VideoManager, SceneManager
from scenedetect.detectors import ContentDetector
from moviepy.video.io.VideoFileClip import VideoFileClip  # ✅ FIXED import
from PIL import Image

# Directories
UPLOAD_FOLDER = 'uploads'
THUMBNAIL_FOLDER = 'thumbnails'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

app = Flask(__name__)
CORS(app)

# Scene detection logic
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
            'start': start_sec,
            'end': end_sec
        })
    return scenes

# Thumbnail generator
def generate_thumbnail(video_path, time_in_seconds, scene_id):
    clip = VideoFileClip(video_path)
    frame = clip.get_frame(time_in_seconds)
    img = Image.fromarray(frame)
    thumb_path = os.path.join(THUMBNAIL_FOLDER, f'{scene_id}.jpg')
    img.save(thumb_path)
    clip.close()
    return thumb_path

# Upload endpoint
@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    file = request.files['video']
    filename = f"{uuid.uuid4().hex}.mp4"
    video_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(video_path)

    # Detect scenes
    scenes = detect_scenes(video_path)

    # Generate thumbnails
    thumbnails = []
    for i, scene in enumerate(scenes):
        start = scene['start']
        scene_id = f"{filename}_{i}"
        thumb_path = generate_thumbnail(video_path, start + 0.1, scene_id)
        thumbnails.append({
            'scene': i,
            'start': round(start, 2),
            'end': round(scene['end'], 2),
            'thumbnail_url': f'/thumbnail/{scene_id}.jpg'
        })

    return jsonify({
        'video': filename,
        'scenes': thumbnails
    })

# Thumbnail endpoint
@app.route('/thumbnail/<thumb_filename>')
def serve_thumbnail(thumb_filename):
    thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_filename)
    if os.path.exists(thumb_path):
        return send_file(thumb_path, mimetype='image/jpeg')
    else:
        return jsonify({'error': 'Thumbnail not found'}), 404

# Health check
@app.route('/status')
def status():
    return jsonify({'status': 'Server is up and running!'})

# Main
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
