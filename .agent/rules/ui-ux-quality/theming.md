## Theming
- Use `next-themes` for theme management.
- Provide `light`, `dark`, and `system` modes.
- Prefer semantic tokens such as `background`, `foreground`, `card`, `muted`, `border`, and `primary`.
- Do not hardcode product colors with raw utility choices like `bg-white`, `text-black`, or literal hex values unless there is a documented exception.
- Every component must remain readable in both light and dark themes.
- Chart styling must follow the active theme.
- Theme switching must not trigger avoidable state loss.
- Light mode should prefer a clean white base or warmer neutral base over a cool blue-gray wash.
- Preserve restrained accent fills and icon accents, but do not tint the whole dashboard as if it were a diagnostics shell.
