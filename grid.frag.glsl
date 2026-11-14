#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D texture;
uniform vec2 textureSize;

varying vec2 vertexPos;

void main()
{
    vec2 posInGrid = floor(vertexPos);
    vec2 posInCell = fract(vertexPos);
    vec2 texCoord = posInGrid / textureSize;

    vec4 color = texture2D(texture, texCoord);

    float fade = 0.005;
    float visibility = 1.0;
    visibility *= smoothstep(0.05, 0.05 + fade, posInCell.x);
    visibility *= 1.0 - smoothstep(0.95, 0.95 + fade, posInCell.x);
    visibility *= smoothstep(0.05, 0.05 + fade, posInCell.y);
    visibility *= 1.0 - smoothstep(0.95, 0.95 + fade, posInCell.y);

    vec4 borderColor = vec4(0.0);

    gl_FragColor = mix(borderColor, color, visibility);
}
