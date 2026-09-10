'use strict';

// Static display values from front matter; these are not live analytics.
// Attach to created dates in Butterfly's post and list metadata without editing the theme.
hexo.extend.filter.register('after_render:html', function (html) {
  const posts = hexo.locals.get('posts').toArray();
  const byDate = new Map(posts.filter(p => Number.isInteger(p.demo_views) && Number.isInteger(p.demo_likes))
    .map(p => [p.date.valueOf(), p]));
  return html.replace(/(?:<span class="post-meta-date">[\s\S]*?<time\b[^>]*>|<time\b[^>]*class="post-meta-date-created"[^>]*>)[\s\S]*?<\/time>/g, time => {
    const datetime = time.match(/datetime="([^"]+)"/);
    const post = datetime && byDate.get(Date.parse(datetime[1]));
    if (!post) return time;
    return time + '<span class="article-demo-stats">'
      + '<span><i class="far fa-eye" aria-hidden="true"></i> 阅读 ' + post.demo_views + '</span>'
      + '<span><i class="far fa-heart" aria-hidden="true"></i> 点赞 ' + post.demo_likes + '</span>'
      + '</span>';
  });
});
