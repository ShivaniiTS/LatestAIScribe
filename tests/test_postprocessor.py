"""
tests/test_postprocessor.py — Tests for the MedASR 12-stage postprocessor.
"""
from postprocessor.medasr_postprocessor import MedASRPostprocessor


def test_basic_cleanup():
    proc = MedASRPostprocessor()
    result = proc.process("The patient  has   pain  in  the  knee.")
    assert "  " not in result.cleaned_text
    assert "knee" in result.cleaned_text


def test_stutter_pairs():
    proc = MedASRPostprocessor()
    result = proc.process("The pat patient has a frac fracture.")
    assert result.metrics.stutter_pairs_merged >= 1
    assert "patient" in result.cleaned_text
    assert "fracture" in result.cleaned_text


def test_filler_normalization():
    proc = MedASRPostprocessor()
    result = proc.process("So uhm uhm the patient came in uh today.")
    assert "[um]" in result.cleaned_text or result.metrics.fillers_normalized > 0


def test_format_command_doubles():
    proc = MedASRPostprocessor()
    result = proc.process("Hello {period period} Next sentence.")
    assert "{period period}" not in result.cleaned_text


def test_punctuation_doubles():
    proc = MedASRPostprocessor()
    result = proc.process("Hello.. World.. End.")
    assert ".." not in result.cleaned_text


def test_offensive_filter():
    proc = MedASRPostprocessor()
    result = proc.process("The patient is a pedophile collector.")
    assert "pedophile" not in result.cleaned_text.lower()
    assert result.metrics.offensive_misrecognitions_removed >= 1


def test_scratch_that():
    proc = MedASRPostprocessor()
    result = proc.process("The patient has scratched that The patient presents with knee pain.")
    assert result.metrics.scratch_that_removed >= 1


def test_medical_phrase_corrections():
    proc = MedASRPostprocessor()
    result = proc.process("The head is normal scalp can be and atraumatic.")
    assert "normocephalic" in result.cleaned_text.lower()


def test_unit_abbreviations():
    proc = MedASRPostprocessor()
    result = proc.process("Take 500 milligrams by mouth twice daily.")
    assert "mg" in result.cleaned_text
    assert "PO" in result.cleaned_text
    assert "BID" in result.cleaned_text


def test_medasr_artifact_removal():
    proc = MedASRPostprocessor()
    result = proc.process("The patient [unintelligible] has [uh] pain.")
    assert "[unintelligible]" not in result.cleaned_text
    assert "[uh]" not in result.cleaned_text


def test_format_command_resolution():
    proc = MedASRPostprocessor()
    result = proc.process("Diagnosis{colon} knee pain{period} Treatment{colon} rest{period}")
    assert "{colon}" not in result.cleaned_text
    assert "{period}" not in result.cleaned_text
    assert ":" in result.cleaned_text
    assert "." in result.cleaned_text


def test_empty_input():
    proc = MedASRPostprocessor()
    result = proc.process("")
    assert result.cleaned_text == ""
    assert result.metrics.words_before == 0


def test_metrics_dict():
    proc = MedASRPostprocessor()
    result = proc.process("Test input.")
    d = result.metrics_dict()
    assert isinstance(d, dict)
    assert "words_before" in d
    assert "words_after" in d


def test_header_cleanup():
    proc = MedASRPostprocessor()
    result = proc.process("[ PAST MEDICAL HISTORY ] The patient has hypertension.")
    # Should still retain the content
    assert "hypertension" in result.cleaned_text


def test_whitespace_normalization():
    proc = MedASRPostprocessor()
    result = proc.process("The   patient\n\n\n\nhas   pain .")
    assert "   " not in result.cleaned_text
    assert " ." not in result.cleaned_text
