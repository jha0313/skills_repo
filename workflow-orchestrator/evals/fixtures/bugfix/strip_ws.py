def normalize(text):
    """공백 정규화: 연속 공백을 하나로 합치고 양끝 공백을 제거한다."""
    return " ".join(text.split(" "))
