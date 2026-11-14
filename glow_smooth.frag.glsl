#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D texture;

uniform vec4 glowColor;
uniform vec2 dimension;
uniform float radius;
uniform vec4 multiplier;

varying vec4 vertexColor;
varying vec2 texCoord;

vec4 outline(vec2 uv, vec2 dxPls, vec2 dyPls, vec2 dxCrs, vec2 dyCrs)
{
    float t = texture2D(texture, uv).a;
    t = max(t, texture2D(texture, (uv + dxPls)).a);
    t = max(t, texture2D(texture, (uv - dxPls)).a);
    t = max(t, texture2D(texture, (uv + dyPls)).a);
    t = max(t, texture2D(texture, (uv - dyPls)).a);
    t = max(t, texture2D(texture, (uv + dxCrs)).a);
    t = max(t, texture2D(texture, (uv - dxCrs)).a);
    t = max(t, texture2D(texture, (uv + dyCrs)).a);
    t = max(t, texture2D(texture, (uv - dyCrs)).a);

    return vec4(vertexColor.rgb, t * vertexColor.a);
}

void main()
{
    vec4 clr = texture2D(texture, texCoord) * multiplier;

    vec2 dxdy = vec2(radius / 3.0, radius / 3.0) / dimension;

    vec2 dxPls = vec2(dxdy.x,  0.0);
    vec2 dyPls = vec2(0.0, -dxdy.y);
    vec2 dxCrs = vec2(-dxdy.x * 0.707106, dxdy.y * 0.707106);
    vec2 dyCrs = dxdy * 0.707106;

    vec4 c = outline(texCoord, dxPls, dyPls, dxCrs, dyCrs) +
        outline(texCoord + dxPls, dxPls, dyPls, dxCrs, dyCrs) +
        outline(texCoord - dxPls, dxPls, dyPls, dxCrs, dyCrs) +
        outline(texCoord + dyPls, dxPls, dyPls, dxCrs, dyCrs) +
        outline(texCoord - dyPls, dxPls, dyPls, dxCrs, dyCrs) +
        outline(texCoord + dxCrs, dxPls, dyPls, dxCrs, dyCrs) +
        outline(texCoord - dxCrs, dxPls, dyPls, dxCrs, dyCrs) +
        outline(texCoord + dyCrs, dxPls, dyPls, dxCrs, dyCrs) +
        outline(texCoord - dyCrs, dxPls, dyPls, dxCrs, dyCrs);

    vec4 blured = (c * vec4(0.125, 0.125, 0.125, 0.15)) * glowColor;

    gl_FragColor = mix(blured, (clr * vertexColor), clr.a);
}