#!/usr/bin/env python3
"""
メタデータ偽装ユーティリティ
AI生成メタデータを除去し、iPhone 15 Pro で撮影したように見える
自然なメタデータを埋め込む。
画像: Pillow + piexif で EXIF を Apple/iPhone に書き換える
動画: ffmpeg で QuickTime メタデータを Apple/iPhone に書き換える
"""

import subprocess
import random
from datetime import datetime, timedelta
from pathlib import Path

import piexif
from PIL import Image


# iPhone 15 Pro のカメラスペック（実機と一致させる）
IPHONE_MAKE      = "Apple"
IPHONE_MODEL     = "iPhone 15 Pro"
IPHONE_SOFTWARE  = "17.5.1"
IPHONE_LENS      = "iPhone 15 Pro back triple camera 6.765mm f/1.78"

# 典型的な iPhone 15 Pro の撮影パラメータ（自然な揺らぎをつける）
FNUMBER_OPTIONS      = [(178, 100), (200, 100), (220, 100)]   # f/1.78, f/2.0, f/2.2
EXPOSURE_OPTIONS     = [(1, 60), (1, 120), (1, 100), (1, 200)]  # 1/60, 1/120, ...
ISO_OPTIONS          = [32, 50, 64, 80, 100, 125]
FOCAL_LENGTH_OPTIONS = [(6765, 1000), (5700, 1000), (13000, 1000)]  # 広角/望遠


def _make_datetime_str(dt: datetime) -> bytes:
    return dt.strftime("%Y:%m:%d %H:%M:%S").encode()


def _random_minute_offset(minutes: int = 5) -> timedelta:
    """撮影時刻に自然な揺らぎを加える"""
    return timedelta(seconds=random.randint(-minutes * 60, minutes * 60))


def inject_iphone_exif(path: Path, shoot_time: datetime = None) -> Path:
    """
    PNG 画像のメタデータを完全に削除したあと
    iPhone 15 Pro で撮影したように見える EXIF を埋め込む。
    shoot_time: 撮影日時（Noneなら現在時刻）
    """
    shoot_dt = (shoot_time or datetime.now()) + _random_minute_offset(3)
    dt_str   = _make_datetime_str(shoot_dt)

    fn_num   = random.choice(FNUMBER_OPTIONS)
    exp      = random.choice(EXPOSURE_OPTIONS)
    iso      = random.choice(ISO_OPTIONS)
    fl       = random.choice(FOCAL_LENGTH_OPTIONS)

    # ピクセルデータのみの新規イメージを作成（元メタデータを一切引き継がない）
    with Image.open(path) as img:
        w, h   = img.size
        clean  = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))

    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make:             IPHONE_MAKE.encode(),
            piexif.ImageIFD.Model:            IPHONE_MODEL.encode(),
            piexif.ImageIFD.Software:         IPHONE_SOFTWARE.encode(),
            piexif.ImageIFD.DateTime:         dt_str,
            piexif.ImageIFD.XResolution:      (72, 1),
            piexif.ImageIFD.YResolution:      (72, 1),
            piexif.ImageIFD.ResolutionUnit:   2,
            piexif.ImageIFD.YCbCrPositioning: 1,
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal:  dt_str,
            piexif.ExifIFD.DateTimeDigitized: dt_str,
            piexif.ExifIFD.ExposureTime:      exp,
            piexif.ExifIFD.FNumber:           fn_num,
            piexif.ExifIFD.ISOSpeedRatings:   iso,
            piexif.ExifIFD.FocalLength:       fl,
            piexif.ExifIFD.LensMake:          IPHONE_MAKE.encode(),
            piexif.ExifIFD.LensModel:         IPHONE_LENS.encode(),
            piexif.ExifIFD.ColorSpace:        1,       # sRGB
            piexif.ExifIFD.PixelXDimension:   w,
            piexif.ExifIFD.PixelYDimension:   h,
            piexif.ExifIFD.Flash:             16,      # 発光なし・強制発光禁止
            piexif.ExifIFD.ExposureProgram:   2,       # 通常プログラム
            piexif.ExifIFD.MeteringMode:      5,       # マルチスポット
            piexif.ExifIFD.WhiteBalance:      0,       # オート
            piexif.ExifIFD.SceneCaptureType:  0,       # 標準
        },
        "1st": {},
        "thumbnail": None,
    }

    exif_bytes = piexif.dump(exif_dict)
    # PNG は EXIF をサポートしないため JPEG に変換して保存
    # Instagram は JPEG を受け付けるのでそのまま使用可能
    jpeg_path = path.with_suffix(".jpg")
    clean.save(str(jpeg_path), format="JPEG", quality=95, exif=exif_bytes)

    # 元の PNG を削除して JPEG のパスを返す
    if jpeg_path != path:
        path.unlink(missing_ok=True)

    return jpeg_path


def strip_image(path: Path, shoot_time: datetime = None) -> Path:
    """
    画像のメタデータを iPhone 15 Pro に置き換える。
    inject_iphone_exif のエイリアス（既存コードとの互換性）。
    """
    return inject_iphone_exif(path, shoot_time)


def strip_video(in_path: Path, out_path: Path = None, shoot_time: datetime = None) -> Path:
    """
    動画のメタデータを除去して iPhone 15 Pro の QuickTime タグに置き換える。
    出力は .mov 固定（MP4 コンテナは make/model タグを保持できないため）。
    -map_metadata -1  : 既存メタデータを全消去
    -metadata ...     : Apple/iPhone タグを注入
    -c copy           : 再エンコードなし（画質劣化なし）
    -movflags +faststart : moov atom を先頭に配置（ストリーミング最適化）
    """
    # 出力は常に .mov（QuickTime コンテナのみ make/model タグを保持できる）
    out = out_path or in_path.with_suffix(".mov").with_stem(in_path.stem + "_iphone")
    dt  = (shoot_time or datetime.now()) + _random_minute_offset(5)
    dt_iso = dt.strftime("%Y-%m-%dT%H:%M:%S.000000Z")

    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(in_path),
            "-map_metadata", "-1",
            "-fflags", "+bitexact",
            # QuickTime / MOV 標準タグ
            "-metadata", f"make={IPHONE_MAKE}",
            "-metadata", f"model={IPHONE_MODEL}",
            "-metadata", f"software={IPHONE_SOFTWARE}",
            "-metadata", f"creation_time={dt_iso}",
            # Apple 固有の QuickTime タグ
            "-metadata", f"com.apple.quicktime.make={IPHONE_MAKE}",
            "-metadata", f"com.apple.quicktime.model={IPHONE_MODEL}",
            "-metadata", f"com.apple.quicktime.software={IPHONE_SOFTWARE}",
            "-metadata", f"com.apple.quicktime.creationdate={dt_iso}",
            "-c:v", "copy",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(out),
        ],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg メタデータ書き換え失敗:\n{result.stderr[-500:]}")

    return out
