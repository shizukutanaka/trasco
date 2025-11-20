# Contributing to Traceo

First off, thank you for considering contributing to Traceo! It's people like you that make Traceo such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps which reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed after following the steps**
* **Explain which behavior you expected to see instead and why**
* **Include screenshots and animated GIFs if possible**
* **Include your OS version, Docker version, and browser**

### Suggesting Enhancements

When creating enhancement suggestions, please include:

* **Use a clear and descriptive title**
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior and expected behavior**
* **Explain why this enhancement would be useful**

### Pull Requests

* Fill in the required template
* Follow the coding standards
* Include appropriate test cases
* Update documentation as needed
* End all files with a newline

## Development Setup

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker and Docker Compose

### Backend Development

```bash
# Install dependencies
cd backend
pip install -r requirements.txt

# Run in development mode
python -m uvicorn app.main:app --reload

# Run tests
pytest
```

### Frontend Development

```bash
# Install dependencies
cd frontend
npm install

# Run in development mode
npm start

# Run tests
npm test

# Build for production
npm run build
```

## Coding Standards

### Python
- Follow PEP 8
- Use type hints where possible
- Write docstrings for functions and classes
- Keep functions small and focused

### JavaScript/React
- Use modern ES6+ syntax
- Use functional components with hooks
- Follow Airbnb JavaScript style guide
- Add JSDoc comments for complex functions

## Translation Contributions

We welcome translations! To add a new language:

1. **Create translation files**:
   - `backend/app/locales/[lang].json`
   - `frontend/src/i18n/[lang].json`
   - `backend/app/templates/abuse/[lang].md`

2. **Update supported languages list** in relevant files

3. **Test your translation**:
   ```bash
   # Set default language
   DEFAULT_LANG=fr docker-compose up -d
   # Visit http://localhost:3000 and verify
   ```

4. **Submit PR** with your translation files

### Translation Guidelines

- Keep the JSON structure identical to `en.json`
- Maintain consistency with existing terminology
- Keep translations concise but complete
- Use professional language appropriate for security context
- For abuse report templates, ensure formal tone

## Commit Messages

* Use the present tense ("Add feature" not "Added feature")
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters or less
* Reference issues and pull requests liberally after the first line
* Consider starting the commit message with an applicable emoji:
    * 🎨 `:art:` when improving the format/structure
    * ⚡ `:zap:` when improving performance
    * 🐛 `:bug:` when fixing a bug
    * ✨ `:sparkles:` when adding a feature
    * 📝 `:memo:` when writing docs
    * 🌍 `:globe_with_meridians:` when adding translations
    * ✅ `:white_check_mark:` when adding tests
    * 🚀 `:rocket:` when deploying or releasing

Example:
```
✨ Add Gmail API integration

- Implement OAuth 2.0 flow
- Add Gmail message parsing
- Support for real-time notifications
Closes #123
```

## Testing

* Write tests for new features
* Ensure all tests pass before submitting PR
* Aim for at least 80% code coverage
* Test edge cases and error scenarios

## Documentation

* Update README.md if you add features
* Add docstrings to functions
* Update API documentation for endpoint changes
* Add examples for complex features

## Security

* Don't commit secrets (API keys, passwords, tokens)
* Always use environment variables for sensitive data
* Follow OWASP security guidelines
* Report security vulnerabilities privately to maintainers

## Review Process

1. One maintainer will review your PR
2. Feedback will be provided for changes needed
3. Once approved, a maintainer will merge your PR
4. Your contribution will be included in the next release

## Community

* Join our discussions on GitHub
* Be respectful and constructive
* Help other community members
* Share your use cases and improvements

## Additional Notes

### Issue and Pull Request Labels

* `bug` - Something isn't working
* `enhancement` - New feature or request
* `documentation` - Improvements or additions to documentation
* `good-first-issue` - Good for newcomers
* `help-wanted` - Extra attention is needed
* `question` - Further information is requested
* `translation` - Language/translation related
* `wontfix` - This will not be worked on
* `duplicate` - This issue or pull request already exists

## Questions?

Feel free to open an issue for any questions or concerns. Our community is here to help!

---

Thank you for contributing to Traceo! 🎉
