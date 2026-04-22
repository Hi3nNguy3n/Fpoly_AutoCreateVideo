import PyPDF2
import os

def extract_text_from_pdf(pdf_path):
    """Trích xuất văn bản từ tệp PDF"""
    text = ""
    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        return f"Lỗi đọc PDF: {str(e)}"

def merge_videos(video_paths, output_path):
    """Ghép danh sách video thành một video duy nhất"""
    from moviepy import VideoFileClip, concatenate_videoclips
    clips = []
    try:
        # Load các video clip
        for path in video_paths:
            if os.path.exists(path):
                clip = VideoFileClip(path)
                clips.append(clip)
            else:
                print(f"Bỏ qua file không tồn tại: {path}")
        
        if not clips:
            return None
            
        # Nối các clip lại với nhau
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # Xuất file video cuối cùng (sử dụng libx264 cho độ tương thích cao)
        final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")
        
        # Đóng các clip để giải phóng bộ nhớ
        for clip in clips:
            clip.close()
            
        return output_path
    except Exception as e:
        print(f"Lỗi ghép video: {str(e)}")
        return None

if __name__ == "__main__":
    # Test (nếu cần)
    pass
