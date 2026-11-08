# Word lists

- `profanity_en.csv`: Surge AI's profanity list (1,598 English words and phrases, with categories and a severity
  rating), as published under the MIT licence (`profanity_en_LICENSE.txt`). Taken unchanged from
  https://github.com/fullfacing/profanity (a copy of https://github.com/surge-ai/profanity). Only its `text` column
  is read: a word in it is an obscene word (`src/obscene.py`).
- `not_obscene.txt`: the words that list catches that are not obscene. Fix a miss here, never in the list.

A change to either file makes every save mark its obscene words again when it opens (`obscene.LIST_VERSION`).
