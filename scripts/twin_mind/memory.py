"""Memory parsing utilities for twin-mind."""


def parse_timeline_entry(entry: dict) -> dict:
    """Parse a timeline entry's preview field into structured data.

    Timeline entries have format:
        preview: "text content\ntitle: Title\nuri: URI\ntags: tag1,tag2"

    Returns dict with: title, text, uri, tags
    """
    preview = entry.get('preview', '')
    uri = entry.get('uri', '')

    # Default values
    result = {
        'title': 'untitled',
        'text': preview,
        'uri': uri or '',
        'tags': [],
        'timestamp': entry.get('timestamp', 0),
        'frame_id': entry.get('frame_id', '')
    }

    # Parse embedded metadata from preview
    lines = preview.split('\n')
    text_lines = []

    for line in lines:
        if line.startswith('title: '):
            result['title'] = line[7:]
        elif line.startswith('uri: '):
            if not result['uri']:
                result['uri'] = line[5:]
        elif line.startswith('tags: '):
            tags_str = line[6:]
            if tags_str:
                result['tags'] = [t.strip() for t in tags_str.split(',') if t.strip()]
        else:
            text_lines.append(line)

    result['text'] = '\n'.join(text_lines).strip()
    return result
