import jellyfish


def levenshtein_similarity(str1, str2):
    return 1 - jellyfish.levenshtein_distance(str1.lower(), str2.lower()) / max(len(str1), len(str2))


def jaro_winkler_similarity(str1, str2):
    return jellyfish.jaro_winkler_similarity(str1.lower(), str2.lower())


def symmetric_sentence_similarity(str1, str2):
    set1 = set(str1.lower().split())
    set2 = set(str2.lower().split())
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    tf_sim1 = intersection / len(set1)
    tf_sim2 = intersection / len(set2)
    symmetric_similarity = (tf_sim1 + tf_sim2) / 2
    return symmetric_similarity


def combined_correctness(submitted_answer, correct_answer, threshold_levenshtein=0.4, threshold_cosine=0.6, symmetric_threshold=0.5):
    levenshtein_sim = levenshtein_similarity(submitted_answer, correct_answer)
    jaccard_sim = jaro_winkler_similarity(submitted_answer, correct_answer)
    symmetric_sim = symmetric_sentence_similarity(submitted_answer, correct_answer)
    return (levenshtein_sim >= threshold_levenshtein or jaccard_sim >= threshold_cosine) and symmetric_sim >= symmetric_threshold
