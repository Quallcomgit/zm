#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D texture;
uniform vec2 textureSize;
uniform float radius;

varying vec2 texCoord;

void main()
{
    vec2 texOffset = 1.0 / textureSize * radius;

    float x = texOffset.x;
    float y = texOffset.y;

    vec4 a = texture2D(texture, vec2(texCoord.x - x, texCoord.y + y));
    vec4 b = texture2D(texture, vec2(texCoord.x,     texCoord.y + y));
    vec4 c = texture2D(texture, vec2(texCoord.x + x, texCoord.y + y));

    vec4 d = texture2D(texture, vec2(texCoord.x - x, texCoord.y));
    vec4 e = texture2D(texture, vec2(texCoord.x,     texCoord.y));
    vec4 f = texture2D(texture, vec2(texCoord.x + x, texCoord.y));

    vec4 g = texture2D(texture, vec2(texCoord.x - x, texCoord.y - y));
    vec4 h = texture2D(texture, vec2(texCoord.x,     texCoord.y - y));
    vec4 i = texture2D(texture, vec2(texCoord.x + x, texCoord.y - y));

    vec4 result = e * 4.0;
    result += (b + d + f + h) * 2.0;
    result += (a + c + g + i);
    result *= 1.0 / 16.0;

    gl_FragColor = result;
}
