# Development Tools
## AI-Powered Internationalization Utilities

This folder contains **development tools** used to create and maintain the "Santa Claus is Calling" application. **They are not required to run the application**, but can be useful for other developers who want to automate similar tasks.

---

## Included Tools

### 1. **parser.py** - Automatic String Extractor

**Purpose**: Automatically extract all user-visible strings from HTML/template files and replace them with variables for internationalization (i18n).

**How it works:**
- Reads an HTML file line by line
- Uses GPT-4 to identify strings that the user will see
- Extracts those strings and replaces them with Flask/Jinja2 variables (`{{ variable_name }}`)
- Saves the processed HTML and a JSON with all extracted strings

**Usage**:
```bash
# From the project root:
python dev-tools/parser.py templates/payment.html

# Optionally, specify the output JSON filename:
python dev-tools/parser.py templates/payment.html custom_strings
```

**Output**:
- `parsed/payment.html` - HTML with variables instead of hardcoded strings
- `parsed/strings.json` - Dictionary with all variables and their strings

**Example**:
```html
<!-- Before: -->
<button>Pay Now</button>

<!-- After: -->
<button>{{ btn_pay_now }}</button>
```

```json
{
    "btn_pay_now": "Pay Now"
}
```

**Advantages**:
- Automates the string extraction process
- GPT-4 generates descriptive variable names
- Detects context to reuse existing variables
- Maintains indentation and format of the original HTML

---

### 2. **strings-translator.py** - Automatic AI Translator

**Purpose**: Automatically translate JSON string files from one language to another using GPT-4.

**How it works:**
- Reads a JSON file with strings in the source language (e.g., Spanish)
- Uses GPT-4 to translate each string to the target language
- Maintains the same variable keys
- Respects already translated strings (doesn't re-translate them)
- Saves the translated JSON in `templates/lang/`

**Usage**:
```bash
# From the project root:
python dev-tools/strings-translator.py strings_es.json strings_en.json

# The language code is automatically extracted from the filename (_en, _es, _fr, etc.)
```

**Output**:
- `templates/lang/strings_en.json` - JSON translated to target language

**Example**:
```json
// Input: strings_es.json
{
    "welcome_message": "Bienvenido a Santa Claus is Calling",
    "btn_start": "Comenzar"
}

// Output: strings_en.json
{
    "welcome_message": "Welcome to Santa Claus is Calling",
    "btn_start": "Start"
}
```

**Advantages**:
- Translates multiple languages automatically
- Maintains consistency in variable names
- Doesn't re-translate already existing strings (saves tokens)
- Supports any language that GPT-4 understands

---

## File Structure

```
dev-tools/
├── README.md                    # This file
├── parser.py                    # String extractor
├── strings-translator.py        # Automatic translator
└── roles/
    ├── parser.txt               # System prompt for parser.py
    └── strings-translator.txt   # System prompt for translator.py
```

---

## Configuration

### Requirements:
1. **Python 3.8+**
2. **Dependencies**:
   ```bash
   pip install openai python-dotenv
   ```

3. **OpenAI API Key**:
   - These tools require an OpenAI API key
   - Make sure you have `OPENAI_KEY` configured in your `.env`
   - They use the `gpt-4-0125-preview` model

### Required environment variables:
```env
OPENAI_KEY=your_openai_api_key
```

---

## Use Cases

### Complete internationalization workflow:

#### Step 1: Extract strings from a template
```bash
python dev-tools/parser.py templates/index.html
```

This generates:
- `parsed/index.html` (with variables)
- `parsed/strings.json` (strings in the source language)

#### Step 2: Copy the base strings.json
```bash
cp parsed/strings.json templates/lang/strings_es.json
```

#### Step 3: Translate to other languages
```bash
# English
python dev-tools/strings-translator.py strings_es.json strings_en.json

# French
python dev-tools/strings-translator.py strings_es.json strings_fr.json

# German
python dev-tools/strings-translator.py strings_es.json strings_de.json

# etc...
```

#### Step 4: Use the processed template
Replace the original template with the parsed one and update your Flask/FastAPI code to load strings based on the user's language.

---

## Why Use These Tools

### Advantages vs. Manual Translation:
1. **Speed**: Translates hundreds of strings in minutes
2. **Consistency**: GPT-4 maintains consistency in terminology
3. **Context**: Understands the application context for better translations
4. **Scalability**: Easy to add new languages
5. **Maintenance**: Only translate new strings, not existing ones

### Advantages vs. Translation Services:
- **More economical**: Pay per API usage instead of subscriptions
- **Faster**: No waiting for human translators
- **Automatable**: Integrable in CI/CD
- **Full control**: You define the prompt and behavior

---

## System Prompts

### parser.txt
Contains instructions for GPT-4 on how to extract strings from HTML code:
- Identify user-visible strings
- Generate descriptive variable names
- Maintain code format and structure
- Reuse variables when strings are identical
- Respect indentation and spaces

### strings-translator.txt
Contains instructions for GPT-4 on how to translate strings:
- Translate preserving meaning and tone
- Maintain Jinja2 placeholders and variables
- Adapt to the cultural context of the target language
- Respect capitalization from context
- Maintain similar length when possible

---

## Limitations and Considerations

### Costs:
- Each execution consumes OpenAI tokens
- `parser.py`: ~100-500 tokens per HTML line
- `strings-translator.py`: ~50-200 tokens per string
- **Tip**: Use on small files or by sections

### Translation quality:
- GPT-4 is very good, but **doesn't replace human review**
- Recommended: Review translations before production
- Especially for legal or critical texts

### Technical limitations:
- Only processes text, doesn't translate images or dynamic content
- Doesn't validate generated code syntax
- Requires internet connection

---

## Important Note

**These tools are optional and do not run automatically.**

The main application ("Santa Claus is Calling") **does NOT depend** on these tools to function. The strings are already extracted and translated in `templates/lang/*.json`.

These tools are useful if:
- You want to add new languages
- You need to update translations
- You're creating new pages/templates
- You want to learn about AI automation

---

## Contact

If you have questions about these tools or want to share improvements, feel free to open an issue in the repository.

---

**Created with GPT-4**
**Part of the "Santa Claus is Calling" project**
