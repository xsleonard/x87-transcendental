"""Apply the frozen generic four-rule scorer to the D0063 one-shot batch."""
from pathlib import Path
import score_d0046_ties as scorer

if __name__ == '__main__':
    scorer.JOB = Path(__file__).resolve().parent.parent / 'tmp/fpatan-re/d0063'
    scorer.main()
