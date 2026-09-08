export function defineField(target, key, value) {
  if (key in target)
    Object.defineProperty(target, key, {
      enumerable: true,
      configurable: true,
      writable: true,
      value,
    });
  else target[key] = value;
  return value;
}
