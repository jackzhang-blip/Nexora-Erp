"""生成 Nexora 内部安装包使用的桌面图标。"""

from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "resources"


def make_icon() -> Image.Image:
    # 在 2048 像素画布上绘制，缩小时线条和圆角依然平滑。
    image = Image.new("RGBA", (2048, 2048), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((96, 96, 1952, 1952), radius=440, fill="#0B69DF")
    draw.rounded_rectangle((118, 118, 1930, 1930), radius=424, outline="#6FC3FF", width=16)
    top = [(1024, 425), (1500, 690), (1024, 965), (548, 690)]
    left = [(548, 748), (990, 1000), (990, 1570), (548, 1320)]
    right = [(1058, 1000), (1500, 748), (1500, 1320), (1058, 1570)]
    draw.polygon(top, fill="#E8F7FF")
    draw.polygon(left, fill="#FFFFFF")
    draw.polygon(right, fill="#90D9FF")
    draw.line([(1024, 1015), (1024, 1570)], fill="#0B69DF", width=32)
    return image.resize((1024, 1024), Image.Resampling.LANCZOS)


def main() -> None:
    RESOURCES.mkdir(exist_ok=True)
    icon = make_icon()
    icon.save(RESOURCES / "icon.png")
    icon.resize((64, 64), Image.Resampling.LANCZOS).save(RESOURCES / "tray.png")
    icon.save(RESOURCES / "icon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    # Pillow 直接写 ICNS，避免依赖不同 macOS 版本的 iconutil 校验行为。
    icon.save(RESOURCES / "icon.icns", format="ICNS")


if __name__ == "__main__":
    main()
