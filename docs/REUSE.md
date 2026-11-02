# 开源复用决策（对齐版 2026-11-02）

**主底座：Whisper-TikTok**（等 Ramon 回 OK 即按此执行；若改 NarratoAI 再说一声）。

## License 对比

| 仓库 | License | Stars | 结论 |
|------|---------|------:|------|
| [MatteoFasulo/Whisper-TikTok](https://github.com/MatteoFasulo/Whisper-TikTok) | **Apache-2.0** | ~344 | **主底座**：edge-tts + Whisper 字幕 + ffmpeg；保留 NOTICE |
| [artbyjazi/autoclip](https://github.com/artbyjazi/autoclip) | **MIT** | ~221 | **辅**：9:16 / 切段思路，不整搬 FastAPI+React |
| [respectfulnrespected59-source/qmm-autoedit](https://github.com/respectfulnrespected59-source/qmm-autoedit) | **MIT** | 0 | **辅**：去静音/切片逻辑参考，不当唯一底座 |
| [linyqh/NarratoAI](https://github.com/linyqh/NarratoAI) | **MIT** | ~1.2万 | 备选（中文解说剪辑很贴工厂素材）；本轮默认不切，除非 Ramon 改选 |

## 复用什么

- Whisper-TikTok：TTS、Whisper→字幕、ffmpeg 烧录/混音  
- autoclip / qmm：切段与 9:16 策略  
- 我们仓库：七步接口、Flet UI、OpenCV 切镜、Windows 字幕路径、PyInstaller  

## 我们只写

部门 Windows UI、多段自有素材 10/15/30 模板、印花钩子文案、安装包胶水；不整仓 fork 重写。

## 下一拍

Ramon：**OK** = Whisper-TikTok；说「改 NarratoAI」则切换。素材到了跑端到端。

## Status

Ramon OK（2026-11-02）。Vendor clone at `/workspace/vendor-whisper-tiktok`，symlink `vendor/Whisper-TikTok`。等素材做端到端。
