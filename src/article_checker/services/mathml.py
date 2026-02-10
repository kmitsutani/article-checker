"""LaTeX to MathML conversion utilities."""

import re
import logging

logger = logging.getLogger(__name__)

# Try to import latex2mathml, provide fallback if not available
try:
    from latex2mathml.converter import convert as latex_to_mathml

    MATHML_AVAILABLE = True
except ImportError:
    MATHML_AVAILABLE = False
    logger.warning("latex2mathml not installed. Math rendering will use fallback.")


def convert_latex_to_mathml(text: str) -> str:
    """
    Convert LaTeX math expressions in text to MathML.

    Supports:
    - Inline math: $...$
    - Display math: $$...$$

    Args:
        text: Text containing LaTeX expressions

    Returns:
        Text with LaTeX converted to MathML
    """
    if not MATHML_AVAILABLE:
        return _fallback_convert(text)

    def replace_display_math(match: re.Match) -> str:
        latex = match.group(1).strip()
        try:
            mathml = latex_to_mathml(latex)
            return f'<div style="text-align: center; margin: 1em 0;">{mathml}</div>'
        except Exception as e:
            logger.debug(f"Failed to convert display math: {latex[:50]}... Error: {e}")
            return f'<div style="text-align: center; margin: 1em 0;"><code>{latex}</code></div>'

    def replace_inline_math(match: re.Match) -> str:
        latex = match.group(1).strip()
        try:
            mathml = latex_to_mathml(latex)
            return mathml
        except Exception as e:
            logger.debug(f"Failed to convert inline math: {latex[:50]}... Error: {e}")
            return f"<code>{latex}</code>"

    # Process display math first ($$...$$)
    text = re.sub(r"\$\$(.*?)\$\$", replace_display_math, text, flags=re.DOTALL)

    # Then process inline math ($...$)
    text = re.sub(r"\$(.*?)\$", replace_inline_math, text)

    return text


def _fallback_convert(text: str) -> str:
    """
    Fallback conversion when latex2mathml is not available.

    Simply wraps LaTeX in <code> tags for display.
    """

    def replace_display(match: re.Match) -> str:
        latex = match.group(1).strip()
        return f'<div style="text-align: center; margin: 1em 0;"><code>{latex}</code></div>'

    def replace_inline(match: re.Match) -> str:
        latex = match.group(1).strip()
        return f"<code>{latex}</code>"

    text = re.sub(r"\$\$(.*?)\$\$", replace_display, text, flags=re.DOTALL)
    text = re.sub(r"\$(.*?)\$", replace_inline, text)

    return text
