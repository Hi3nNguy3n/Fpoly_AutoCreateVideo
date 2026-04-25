# Sử dụng Python 3.10 slim
FROM python:3.10-slim

# 1. Cài đặt các thư viện hệ thống cần thiết (Đã thêm xvfb để chạy màn hình ảo)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ffmpeg \
    xvfb \
    libgbm-dev \
    libnss3 \
    libasound2 \
    libxss1 \
    libxtst6 \
    libgtk-3-0 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Tạo thư mục trình duyệt dùng chung và cấp quyền tuyệt đối
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir /ms-playwright && chmod 777 /ms-playwright

# 3. Thiết lập thư mục làm việc
WORKDIR /app

# 4. Copy và cài đặt các thư viện Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Cài đặt trình duyệt Playwright vào thư mục dùng chung
RUN playwright install chromium
RUN playwright install-deps chromium

# 6. Thiết lập User và cấp quyền sở hữu thư mục (Làm bằng quyền Root)
RUN useradd -m -u 1000 user
# Tạo thư mục output và phân quyền cho user 1000 TRƯỚC KHI chuyển sang USER user
RUN mkdir -p /app/output_videos /app/Final_Videos && chown -R user:user /app

# 7. Chuyển sang dùng User hạn chế của Hugging Face
USER user
COPY --chown=user . .

# 8. Cấu hình biến môi trường cho Streamlit
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Mở cổng 7860
EXPOSE 7860

# 9. Chạy Streamlit với màn hình ảo xvfb-run
CMD ["xvfb-run", "streamlit", "run", "app.py", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
