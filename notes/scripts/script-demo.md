# Script Demo

This is a demo on how to use the plugin obsidian-execute-code to execute code blocks in Obsidian.

Tags: #script #demo

## Python

We can run some python code

```python
x = 5
```

And it will hold state between code blocks, so we can access the variable `x` in another code block.

```python
print(x)
```

## Bash

We can also access the terminal and run bash commands. For example, we can navigate to the attachments folder and open an image.

```bash
cd $HOME/dsf/repos/dsf-brain/attachments

open argocd-icon.png
```

## References

- [obsidian-execute-code](https://github.com/twibiral/obsidian-execute-code)

