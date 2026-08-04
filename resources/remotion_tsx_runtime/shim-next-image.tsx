import React from "react";

export default function Image(props: Record<string, any>) {
  const { fill, priority, quality, ...rest } = props;
  const style = fill
    ? { position: "absolute", inset: 0, width: "100%", height: "100%", ...(rest.style || {}) }
    : rest.style;
  return <img {...rest} style={style} />;
}
