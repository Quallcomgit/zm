#ifdef GL_ES
precision mediump float;
#endif

[Editable]
uniform float power;

// Center задается в uv координатах
[Editable]
uniform vec2 center;

[Editable]
uniform float inner_radius;

[Editable]
uniform float outer_radius;

uniform sampler2D texture;

varying vec4 vertexColor;
varying vec2 texCoord;

void main()
{
    vec2 xy = texCoord;
    vec2 direction = xy - center;
    float distance = sqrt(dot(direction, direction));

    float bind;
    if(power > 0.0)
    {
        bind = sqrt(dot(center, center));
    }
    else
    {
        bind = center.x;
    }

    vec2 uv;
    if(power > 0.0)
    {
        uv = center + normalize(direction) * tan(distance * power) * bind / tan(bind * power);
    }
    else if(power < 0.0)
    {
        uv = center + normalize(direction) * atan(distance * -power * 10.0) * bind / atan(-power * bind * 10.0);
    }
    else
    {
        uv = texCoord;
    }

    float factor = smoothstep(outer_radius / 2.0, inner_radius / 2.0, distance);
    uv = mix(texCoord, uv, factor);

    gl_FragColor = texture2D(texture, uv) * vertexColor;
}