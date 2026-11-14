#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D texture;
uniform vec2 textureSize;
uniform float radius;
uniform float kernelMultiplier;

varying vec2 texCoord;

void main()
{
    vec2 texOffset = 1.0 / textureSize * radius;

    float x = texOffset.x;
    float y = texOffset.y;

    vec4 a = texture2D(texture, vec2(texCoord.x, texCoord.y));

    vec4 b = texture2D(texture, vec2(texCoord.x, texCoord.y + y * 2.0));
    vec4 c = texture2D(texture, vec2(texCoord.x, texCoord.y - y * 2.0));
    vec4 d = texture2D(texture, vec2(texCoord.x - x * 2.0, texCoord.y));
    vec4 e = texture2D(texture, vec2(texCoord.x + x * 2.0, texCoord.y));

    vec4 f = texture2D(texture, vec2(texCoord.x - x, texCoord.y + y));
    vec4 j = texture2D(texture, vec2(texCoord.x + x, texCoord.y + y));
    vec4 h = texture2D(texture, vec2(texCoord.x - x, texCoord.y - y));
    vec4 i = texture2D(texture, vec2(texCoord.x + x, texCoord.y - y));

    vec4 result = a * 4.0 * kernelMultiplier;
    result += (b + c + d + e) * kernelMultiplier;
    result += (f + j + h + i) * 2.0 * kernelMultiplier;

    gl_FragColor = result / 16.0;
}
