# Contributing to CDOps Cloud Zombie Hunter

First off, thank you for considering contributing to CDOps Cloud Zombie Hunter! 🎉

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues to avoid duplicates. When you create a bug report, include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples** (command you ran, expected output, actual output)
- **Describe the behavior you observed** and explain which behavior you expected to see and why
- **Include details about your configuration and environment**:
  - Python version (`python --version`)
  - Operating system
  - AWS region(s) scanned
  - boto3 version

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion:

- **Use a clear and descriptive title**
- **Provide a detailed description of the suggested enhancement**
- **Explain why this enhancement would be useful** to most users
- **List any alternative solutions or features** you've considered

### Pull Requests

1. **Fork the repository** and create your branch from `main`
2. **Make your changes** with clear, commented code
3. **Test thoroughly** - ensure the tool still works with your changes
4. **Follow the existing code style** - match indentation, naming conventions, etc.
5. **Update documentation** if you're adding features
6. **Write a clear commit message** describing what you changed and why

#### Pull Request Process

1. Ensure your code passes basic testing (run against test AWS environment if possible)
2. Update the README.md with details of changes if applicable
3. The PR will be reviewed by maintainers
4. Once approved, your contribution will be merged!

## Code Style Guidelines

- Follow PEP 8 style guidelines for Python
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Include comments for complex logic
- Keep functions focused on a single responsibility
- Handle exceptions gracefully with informative messages

## Adding New Resource Scanners

If you want to add support for scanning new AWS resource types:

1. Create a new method in the `ZombieHunter` class following this pattern:
   ```python
   def scan_new_resource_type(self, region: str) -> List[Dict[str, Any]]:
       """
       Scan for [description of zombie condition].
       
       Args:
           region: AWS region to scan
           
       Returns:
           List of dictionaries containing zombie resource details
       """
   ```

2. Use try/except blocks to handle permission errors gracefully
3. Add findings to `self.findings` list
4. Update `self.scan_summary` dictionary with a new counter
5. Call your new method from `run_scan()`
6. Update the README.md with information about the new resource type
7. Update `iam-policy.json` if new permissions are required

## Testing

Before submitting a PR:

1. Test in at least one AWS region
2. Test with and without required permissions (to verify graceful error handling)
3. Test the `--verbose` flag
4. Verify CSV export works correctly
5. Check that the output formatting looks clean

## Questions?

Feel free to open an issue with the "question" label, or reach out to us at contact@cdops.tech

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and encourage diverse contributions
- Focus on constructive feedback
- Assume good intentions

---

Thank you for contributing to making cloud cost optimization accessible to everyone! 🚀
