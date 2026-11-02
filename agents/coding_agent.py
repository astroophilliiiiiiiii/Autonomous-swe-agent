from langchain_core.prompts import ChatPromptTemplate

def create_coding_agent(llm):
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a software engineer working on an existing repository.

Given the task, problem analysis, relevant file contents, and previous
test failure feedback, modify the necessary code.

CRITICAL INSTRUCTION:
- Your output must start directly with '{{' and end with '}}'.
- Do NOT write any introduction, greeting, or explanation.
- Do NOT use markdown code fences like ```json or ```.

Return ONLY valid JSON in this exact format:
{{
  "files": [
    {{
      "path": "relative/path/to/file.py",
      "content": "complete updated file content"
    }}
  ]
}}

Rules:
- Include every modified file in the response.
- Each content value must contain the COMPLETE updated file.
- You may modify files provided in the input AND create new files (e.g. test files) when the task requires it.
- New file paths must be relative to the repo root and must not escape it (no '..' or absolute paths).
- Preserve unrelated code and existing functionality.
- CRITICAL FOR JSON VALIDITY: In Python code inside "content", prefer single quotes '...' for strings (e.g., 'Mouse', 'name', dict(category='test')) to prevent unescaped double quotes from corrupting the JSON. Any double quotes inside "content" MUST be escaped as \\".
- Ensure the JSON is 100% valid syntax.
        """),
        ("human", """Task: {task}

Problem analysis: {analysis}

Relevant file contents: {file_contents}

Previous test failure feedback: {error_feedback}
        """),
    ])

    return prompt | llm
