/** The n highest scores, highest first. Does not change the input array. */
export function topScores(scores, n) {
  return [...scores].sort().reverse().slice(0, n);
}

export function rankOf(scores, score) {
  return topScores(scores, scores.length).indexOf(score) + 1;
}
