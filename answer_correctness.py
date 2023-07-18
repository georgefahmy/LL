from thefuzz import fuzz

def levenshtein_similarity(str1, str2):
    return fuzz.partial_ratio(str1.lower(), str2.lower()) / 100

def jaro_winkler_similarity(str1, str2):
    return fuzz.token_sort_ratio(str1.lower(), str2.lower()) / 100


def combined_correctness(sa,ca,debug=False,threshold_levenshtein=0.5,threshold_jaro=0.6):
    levenshtein_sim = levenshtein_similarity(sa, ca)
    jaro_winkler_sim = jaro_winkler_similarity(sa, ca)
    if debug:
        print(f"levenshtein similarity: {levenshtein_sim}, threshold: {threshold_levenshtein}")
        print(f"jaro_winkler similarity: {jaro_winkler_sim}, threshold: {threshold_jaro}")
    return levenshtein_sim >= threshold_levenshtein or jaro_winkler_sim >= threshold_jaro
