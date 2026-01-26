from pathlib import Path
import re
from typing import Dict, Optional


class PathTemplate:
    TAGS = {
        '<t:service>': 'service',
        '<t:creator>': 'creator',
        '<t:post>': 'post',
        '<t:index>': 'index',
        '<t:filename>': 'filename',
        '<t:filehash>': 'filehash',
        '<t:extension>': 'extension',
        '<t:date>' : 'date',
        '<t:id>' : 'id'
    }

    def __init__(self, template_str: str, output_dir: Path):
        self.template_str = template_str
        self.output_dir = output_dir

    def format(self, context: Dict[str, str]) -> Path:
        """
        args: context: dict. containing values for template tags, keys should match TAGS values above
        returns: path: the formatted path
        """

        result = self.template_str
        for tag, key in self.TAGS.items():
            value = context.get(key, '')
            if value is None:
                value = ''
            result = result.replace(tag, str(value))

        result = self.sanitize_path(result)

        return self.output_dir / result

    @staticmethod
    def sanitize_path(path_str: str) -> str:
        """
        replaces all invalid path characters with underscores
        invalid characters for windows: <>:"/\|?*
        """
        invalid = r'[<>:"|?*]'
        path_str = re.sub(invalid, '_', path_str)
        parts = path_str.split('/')
        parts = [p.strip('.') for p in parts if p.strip('.')]
        return '/'.join(parts)


class TemplateManager:
    def __init__(self, output_dir: Path,
                 default_template: Optional[str] = None,
                 image_template: Optional[str] = None,
                 video_template: Optional[str] = None):
        self.output_dir = output_dir

        if default_template is None:
            default_template = "<ks:creator>/<ks:filename><ks:extension>"

        self.default_template = PathTemplate(default_template, output_dir)
        self.image_template = PathTemplate(image_template, output_dir) if image_template else None
        self.video_template = PathTemplate(video_template, output_dir) if video_template else None

    def get_path(self, context: Dict[str, str], is_image: bool = False, is_video: bool = False) -> Path:
        if is_image and self.image_template:
            return self.image_template.format(context)
        elif is_video and self.video_template:
            return self.video_template.format(context)
        else:
            return self.default_template.format(context)