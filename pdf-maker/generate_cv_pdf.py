from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, KeepTogether
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import re
import yaml
from reportlab.platypus import FrameBreak

MD_FILE = 'CV_optimized_ATS.md'
OUT_FILE = 'Stephanie_Manrique_CV.pdf'
CONFIG_FILE = 'cv_template_rules.yaml'

def load_config(config_path):
    """Load configuration from YAML file."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Warning: {config_path} not found, using defaults")
        return {}
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}

def read_markdown_sections(path):
    """Parse markdown file into sections, handling ## and ### headers properly."""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()

    sections = {}
    current_section = 'HEADER'
    current_subsection = None
    buffer = []

    for line in lines:
        if line.startswith('## '):
            # Save previous section
            if buffer:
                if current_subsection:
                    sections.setdefault(current_section, {})[current_subsection] = '\n'.join(buffer).strip()
                else:
                    sections[current_section] = '\n'.join(buffer).strip()

            # Start new section
            current_section = line.strip('# ').strip()
            current_subsection = None
            buffer = []

        elif line.startswith('### '):
            # Save previous subsection content
            if buffer and current_subsection:
                sections.setdefault(current_section, {})[current_subsection] = '\n'.join(buffer).strip()
            elif buffer and not current_subsection:
                # Content before first subsection
                sections.setdefault(current_section, {'_intro': '\n'.join(buffer).strip()})

            # Start new subsection
            current_subsection = line.strip('# ').strip()
            sections.setdefault(current_section, {})
            buffer = []

        else:
            buffer.append(line)

    # Save final content
    if buffer:
        if current_subsection:
            sections.setdefault(current_section, {})[current_subsection] = '\n'.join(buffer).strip()
        else:
            sections[current_section] = '\n'.join(buffer).strip()

    return sections

def mk_para(text, style, subsection_style=None):
    """Convert markdown text to ReportLab paragraphs, handling bullets, formatting, and subsections."""
    flows = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            flows.append(Spacer(1, 4))
        elif line.startswith('- '):
            # Handle bullet points with markdown formatting
            bullet_text = line[2:].strip()
            formatted_text = format_markdown_text(bullet_text)
            flows.append(Paragraph('&#8226; ' + formatted_text, style))
        else:
            # Handle regular text with markdown formatting
            formatted_text = format_markdown_text(line)
            flows.append(Paragraph(formatted_text, style))
    return flows

def format_markdown_text(text):
    """Convert markdown formatting to ReportLab HTML-like tags."""
    # Handle bold text **text**
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    
    # Handle italic text *text* (but not already processed bold)
    text = re.sub(r'(?<!</b>)\*([^*]+)\*(?!<b>)', r'<i>\1</i>', text)
    
    # Handle inline code `text`
    text = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', text)
    
    # Handle links [text](url) - convert to just the text for now
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Handle em dashes and en dashes
    text = text.replace('—', '&#8212;')
    text = text.replace('–', '&#8211;')
    
    # Handle special characters that might cause issues
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    
    # But restore our formatting tags
    text = text.replace('&lt;b&gt;', '<b>').replace('&lt;/b&gt;', '</b>')
    text = text.replace('&lt;i&gt;', '<i>').replace('&lt;/i&gt;', '</i>')
    text = text.replace('&lt;font', '<font').replace('&lt;/font&gt;', '</font>')
    
    return text

def match_section_name(section_name, target_sections, config):
    """Flexibly match section names to target categories using config mapping."""
    section_lower = section_name.lower()
    
    # Get mapping from config or use defaults
    md_mapping = config.get('md_mapping', {})
    headings_map = md_mapping.get('headings_map', {})
    
    # Try exact mapping first
    for md_heading, target in headings_map.items():
        clean_heading = md_heading.replace('## ', '').lower()
        if clean_heading in section_lower or section_lower in clean_heading:
            if target in target_sections:
                return target
    
    # Fallback to flexible matching
    matches = {
        'experience': ['experience', 'work experience', 'professional experience', 'employment'],
        'projects': ['projects', 'relevant projects', 'key projects', 'hackathons', 'hackatons'],
        'education': ['education', 'academic background', 'qualifications'],
        'summary': ['summary', 'professional summary', 'profile', 'about'],
        'skills': ['skills', 'technical skills', 'core competencies', 'abilities'],
        'key_achievements': ['achievements', 'accomplishments', 'awards', 'key achievements'],
        'languages': ['languages', 'language skills'],
        'contact': ['contact', 'contact information'],
        'certifications': ['certifications', 'certification', 'certificates']
    }

    for target in target_sections:
        if target in matches and any(variant in section_lower for variant in matches[target]):
            return target
    return None

def build_story_with_layout(sections, config):
    """Build the document story with proper layout and styling from config."""
    # Get colors from config
    colors_config = config.get('colors', {})
    fonts_config = config.get('fonts', {})
    body_config = config.get('body', {})
    
    # Color setup
    text_primary = colors.HexColor(colors_config.get('text_primary', '#111827'))
    accent_primary = colors.HexColor(colors_config.get('accent_primary', '#2EBCC6'))
    text_muted = colors.HexColor(colors_config.get('text_muted', '#4B5563'))
    
    # Font setup
    font_family = fonts_config.get('family_stack', ['Helvetica'])[0]
    if 'Inter' in font_family or 'SF Pro' in font_family:
        font_family = 'Helvetica'  # Fallback to available font
    
    font_sizes = fonts_config.get('sizes_pt', {})
    font_weights = fonts_config.get('weight', {})
    
    # Create styles based on config
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'],
                                fontName=f'{font_family}-Bold', 
                                fontSize=font_sizes.get('name', 30), 
                                leading=font_sizes.get('name', 30) * 1.1,
                                textColor=text_primary)
    
    h2_style = ParagraphStyle('H2', parent=styles['Heading2'],
                             fontName=f'{font_family}-Bold', 
                             fontSize=font_sizes.get('section_heading', 10.5), 
                             leading=font_sizes.get('section_heading', 10.5) * 1.2,
                             textColor=text_primary, spaceBefore=8, spaceAfter=4)
    
    h3_style = ParagraphStyle('H3', parent=styles['Heading3'],
                             fontName=f'{font_family}-Bold', 
                             fontSize=font_sizes.get('body', 9.6), 
                             leading=font_sizes.get('body', 9.6) * 1.2,
                             textColor=accent_primary, spaceBefore=6, spaceAfter=3)
    
    normal_style = ParagraphStyle('Normal', parent=styles['Normal'],
                                 fontName=font_family, 
                                 fontSize=font_sizes.get('body', 9.6), 
                                 leading=font_sizes.get('body', 9.6) * 1.25,
                                 textColor=text_primary)
    
    small_style = ParagraphStyle('Small', parent=styles['Normal'],
                                fontName=font_family, 
                                fontSize=font_sizes.get('small', 8.6), 
                                leading=font_sizes.get('small', 8.6) * 1.25,
                                textColor=text_primary)

    # Extract header/title
    header_content = []
    if 'HEADER' in sections:
        header_text = sections['HEADER']
        if isinstance(header_text, str):
            lines = header_text.split('\n')
            title_added = False
            for line in lines:
                line = line.strip()
                if line and line.startswith('#'):
                    # Main title
                    title = line.strip('# ').strip()
                    if title and not title_added:
                        header_content.append(Paragraph(title, title_style))
                        title_added = True
                elif line.startswith('**') and line.endswith('**'):
                    # Subtitle (like **Software Engineer Intern**)
                    subtitle = line.strip('*').strip()
                    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
                                                   fontName=f'{font_family}', 
                                                   fontSize=font_sizes.get('title', 12.5), 
                                                   leading=font_sizes.get('title', 12.5) * 1.2,
                                                   textColor=accent_primary)
                    header_content.append(Paragraph(subtitle, subtitle_style))
                elif line and title_added:
                    # Other header content (could be contact info, etc.)
                    formatted_line = format_markdown_text(line)
                    contact_style = ParagraphStyle('Contact', parent=styles['Normal'],
                                                 fontName=font_family, 
                                                 fontSize=font_sizes.get('contact', 9.5), 
                                                 leading=font_sizes.get('contact', 9.5) * 1.2,
                                                 textColor=text_muted)
                    header_content.append(Paragraph(formatted_line, contact_style))

    # Get column order from config
    columns_config = body_config.get('columns', {})
    order_config = body_config.get('order', {})
    
    left_order = order_config.get('left', ['experience', 'education', 'languages'])
    right_order = order_config.get('right', ['summary', 'key_achievements', 'skills', 'certifications'])
    
    # Organize sections into left and right columns
    left_flow = []
    right_flow = []

    def add_section_content(section_name, section_data, flow, use_small_style=False):
        style = small_style if use_small_style else normal_style

        # Add section header (uppercase as per config)
        section_heading_text = section_name.upper()
        flow.append(Paragraph(section_heading_text, h2_style))

        if isinstance(section_data, dict):
            # Handle subsections (like Professional Experience with multiple jobs)
            for subsection_name, subsection_content in section_data.items():
                if subsection_name == '_intro':
                    # Content before first subsection
                    flow.extend(mk_para(subsection_content, style))
                else:
                    # Subsection header (### level)
                    flow.append(Paragraph(subsection_name, h3_style))
                    flow.extend(mk_para(subsection_content, style))
                flow.append(Spacer(1, 4))
        else:
            # Simple section content
            flow.extend(mk_para(section_data, style))
            flow.append(Spacer(1, 6))

    # Add left column sections
    for target in left_order:
        for section_name, section_data in sections.items():
            if section_name == 'HEADER':
                continue
            if match_section_name(section_name, [target], config):
                add_section_content(section_name, section_data, left_flow, use_small_style=False)
                break

    # Add right column sections  
    for target in right_order:
        for section_name, section_data in sections.items():
            if section_name == 'HEADER':
                continue
            if match_section_name(section_name, [target], config):
                add_section_content(section_name, section_data, right_flow, use_small_style=True)
                break

    return header_content, left_flow, right_flow


if __name__ == '__main__':
    # Load configuration
    config = load_config(CONFIG_FILE)
    
    # Read and parse markdown sections
    sections = read_markdown_sections(MD_FILE)
    
    # Build document content with layout
    header_content, left_flow, right_flow = build_story_with_layout(sections, config)
    
    # Get layout configuration from YAML
    page_config = config.get('page', {})
    body_config = config.get('body', {})
    colors_config = config.get('colors', {})
    
    # Page margins from config (convert to mm)
    margins = page_config.get('margins_mm', {'top': 16, 'right': 16, 'bottom': 16, 'left': 16})
    left_margin = margins.get('left', 16) * mm
    right_margin = margins.get('right', 16) * mm
    top_margin = margins.get('top', 16) * mm
    bottom_margin = margins.get('bottom', 16) * mm
    
    # Column ratios from config
    columns_config = body_config.get('columns', {})
    left_ratio = columns_config.get('left_width', 0.62)
    right_ratio = columns_config.get('right_width', 0.38)
    
    # Background colors from config
    page_bg = colors.HexColor(page_config.get('background', {}).get('color', '#F7FAFF'))
    card_bg = colors.HexColor(page_config.get('background', {}).get('card', {}).get('color', '#FFFFFF'))
    
    # Page setup
    page_w, page_h = A4

    # Calculate column widths
    total_inner_width = page_w - left_margin - right_margin
    s = left_ratio + right_ratio
    left_w = total_inner_width * (left_ratio / s)
    right_w = total_inner_width * (right_ratio / s)
    gutter = body_config.get('gutters_mm', 8) * mm

    # Create document
    doc = BaseDocTemplate(OUT_FILE, pagesize=A4,
                          leftMargin=left_margin, rightMargin=right_margin,
                          topMargin=top_margin, bottomMargin=bottom_margin)

    # Create frames for header and two columns
    # Calculate header height dynamically based on content
    fonts_config = config.get('fonts', {})
    font_sizes = fonts_config.get('sizes_pt', {})
    
    if header_content:
        # Estimate height based on number of elements and font sizes
        estimated_lines = len(header_content)
        title_height = font_sizes.get('name', 30) * 1.2  # Title line height
        subtitle_height = font_sizes.get('title', 12.5) * 1.2  # Subtitle line height
        contact_height = font_sizes.get('contact', 9.5) * 1.2  # Contact line height
        
        # Calculate approximate header height (convert to mm)
        header_height_pts = title_height + subtitle_height + (contact_height * max(0, estimated_lines - 2)) + 10
        header_height = max(25*mm, min(header_height_pts * 0.35, 50*mm))  # Convert pts to mm (approx 0.35mm per pt)
    else:
        header_height = 25*mm  # Minimum header height if no content
    
    content_height = page_h - top_margin - bottom_margin - header_height
    
    header_frame = Frame(left_margin, page_h - top_margin - header_height,
                        total_inner_width, header_height, id='header', showBoundary=0)
    left_frame = Frame(left_margin, bottom_margin,
                      left_w - gutter/2, content_height,
                      id='left', showBoundary=0)
    right_frame = Frame(left_margin + left_w + gutter/2, bottom_margin,
                       right_w - gutter/2, content_height,
                       id='right', showBoundary=0)

    def on_page(canvas, doc):
        # Draw page background
        canvas.saveState()
        canvas.setFillColor(page_bg)
        canvas.rect(0, 0, page_w, page_h, stroke=0, fill=1)
        
        # Draw card background (white card on colored background)
        card_config = page_config.get('background', {}).get('card', {})
        if card_config.get('radius_mm', 0) > 0:
            # For now, draw as rectangle (rounded corners would need more complex code)
            canvas.setFillColor(card_bg)
            canvas.rect(left_margin - 5*mm, bottom_margin - 5*mm, 
                       total_inner_width + 10*mm, page_h - top_margin - bottom_margin + 10*mm, 
                       stroke=0, fill=1)
        
        canvas.restoreState()

    # Create page template with three frames
    template = PageTemplate(id='CV', frames=[header_frame, left_frame, right_frame], onPage=on_page)
    doc.addPageTemplates([template])

    # Build the complete story
    story = []
    
    # Add header content
    if header_content:
        story.extend(header_content)
    
    # Break to left column
    story.append(FrameBreak())
    if left_flow:
        story.extend(left_flow)
    
    # Break to right column
    story.append(FrameBreak())
    if right_flow:
        story.extend(right_flow)

    # Build PDF
    doc.build(story)
    print('PDF generated:', OUT_FILE)
