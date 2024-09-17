# llama-reasoning

This is my attempt at making a llama model that can reason. Inspired by OpenAI O1 reasoning model.

Rule of thumb:
- For massive refactoring jobs or green fielding a massive project, use o1-mini. The combination of deeper thinking and massive output token limits allows for one-shot completion.
- For a collection of smaller tasks, Claude Sonnet 3.5 remains the preferred choice among closed source coding LLMs.
- Be very specific and overly verbose in the prompt to o1-mini. Describe the task in as much detail as possible. This will save time as this model is not intended for conversations or fixing small bugs. It is akin to a Ferrari compared to the Honda that is Sonnet.

# References
- https://github.com/hijkzzz/Awesome-LLM-Strawberry
  