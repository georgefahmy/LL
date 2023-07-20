from rapidfuzz import fuzz
import spacy


nlp = spacy.load("en_core_web_md")


def spacy_similarity(str1, str2):
    # Process the input sentences with spaCy
    doc1 = nlp(str1.lower())
    doc2 = nlp(str2.lower())
    # Calculate the similarity between the processed sentences
    similarity_score = doc1.similarity(doc2)
    return similarity_score


def levenshtein_similarity(str1, str2):
    return fuzz.partial_ratio(str1.lower(), str2.lower()) / 100


def jaro_winkler_similarity(str1, str2):
    return fuzz.token_sort_ratio(str1.lower(), str2.lower()) / 100


def combined_correctness(
    sa, ca, debug=False, threshold_levenshtein=0.6, threshold_jaro=0.6, spacy_threshold=0.6
):
    levenshtein_sim = levenshtein_similarity(sa, ca)
    jaro_winkler_sim = jaro_winkler_similarity(sa, ca)
    spacy_sim = spacy_similarity(sa, ca)
    if debug:
        print(
            f"SpaCy similarity: {spacy_sim}, threshold: {spacy_threshold}\n"
            + f"Levenshtein similarity: {levenshtein_sim}, threshold: {threshold_levenshtein}\n"
            + f"Jaro Winkler similarity: {jaro_winkler_sim}, threshold: {threshold_jaro}"
        )
    return (
        levenshtein_sim > threshold_levenshtein or jaro_winkler_sim > threshold_jaro
    ) or spacy_sim > spacy_threshold
