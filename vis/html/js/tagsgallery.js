/**
 * @fileoverview js Gallery of tags.
 *
 * @author (cesarpalomo@gmail.com) Cesar Palomo
 */



/**
 * Manages a list of tags used for pages (some predefined and some defined by user).
 * Interaction is possible through click on "tag selected" and "untag selected".
 *
 * @param parentContainerId ID for gallery parent div element.
 * @param predefinedTags list of predefined tags, with tag name.
 * @param tagsLogic mechanism to handle tags logic: some tags are not applicable, and some tags when
 *        applied should trigger the removal of other tags (e.g. when Yes is applied, No is
 *        removed).
 *        Must be in the format:
 *         {
 *           'TagName': {
 *             applicable: true/false,
 *             removable: true/false,
 *             negate: ['Tag1', 'Tag2'],
 *           },
 *         }
 */
var TagsGallery = function(parentContainerId, predefinedTags, tagsLogic) {
  this.parentContainerId = parentContainerId;

  // Predefined items in gallery.
  this.predefinedItems = predefinedTags;

  // User-defined items in gallery.
  this.userItems = [];

  // Handles tags logic.
  this.tagsLogic = tagsLogic;

  this.update();
};


/**
 * Clears list of items.
 */
TagsGallery.prototype.clear = function(lazyUpdate) {
  this.userItems = [];

  if (!lazyUpdate) {
    this.update();
  }
};


/**
 * Adds item to gallery.
 */
TagsGallery.prototype.addItem = function(tag, lazyUpdate) {
  this.userItems.push(tag);
  this.tagsLogic[tag] = {'applicable': true, 'removable': true, negate: []};
  if (!lazyUpdate) {
    this.update();
  }
};


/**
 * Sets mechanism to handle tags logic: some tags are not applicable, and some tags when applied
 * should trigger the removal of other tags (e.g. when Yes is applied, No is removed).
 * Logic must be in the format:
 *  {
 *    'TagName': {
 *      applicable: true/false,
 *      removable: true/false,
 *      negate: ['Tag1', 'Tag2'],
 *    },
 *  }
 */
TagsGallery.prototype.setTagsLogic = function(tagsLogic) {
  // Handles tags logic.
  this.tagsLogic = tagsLogic;
};


/**
 * Updates gallery.
 */
TagsGallery.prototype.update = function() {
  var gallery = this;
  this.items = this.predefinedItems.concat(this.userItems);

  var gallery = this;
  var items = d3.select(this.parentContainerId)
    .selectAll('.item').data(this.items, function(item, i) {
      return item + '-' + i;
  });

  // New items.
  items.enter()
    .append('div')
    .classed('noselect', true)
    .classed('item', true);

  // Remove missing items.
  items.exit().remove();

  // Updates existing items.
  items
    .on('click', function(item, i) {
      var itemElm = d3.select(this);
      itemElm.classed('selected', !itemElm.classed('selected'));
      gallery.onItemClick(item, i);
    })
    .on('mouseover', function(item, i) {
      gallery.onItemFocus(item, i, true);
      d3.select(this).selectAll('img').classed('focus', true);
    })
    .on('mouseout', function(item, i) {
      Utils.hideTooltip();
      d3.select(this).selectAll('img').classed('focus', false);
      gallery.onItemFocus(item, i, false);
    })
    .html(function(item, i) {
      return gallery.getItemButtons(item, i) + gallery.getItemInfo(item, i);
    });

  // Configures actions on images.
  items.each(function(item, i) {
    // Only clickable tags.
    var isApplicable = gallery.isTagApplicable(item);
    var isRemovable = gallery.isTagRemovable(item);

    if (isApplicable || isRemovable) {
      var itemElm = d3.select(this);
      itemElm.selectAll('img').each(function() {
        var img = d3.select(this);
        var actionType = img.attr('actionType');
        if ((isApplicable && actionType == 'Apply') 
            || (isRemovable && actionType == 'Remove')) {
          img
            .on('mouseover', function() {
              Utils.showTooltip();
            })
            .on('mousemove', function() {
              Utils.updateTooltip(actionType + ' tag "' + item + '"');
            })
            .on('mouseout', function() {
              Utils.hideTooltip();
            })
            .on('click', function() {
              gallery.onItemActionClick(item, i, actionType);
              event.stopPropagation();
            });
        }
      });
    }
  });
};


/**
 * Returns whether a tag is applicable.
 */
TagsGallery.prototype.isTagApplicable = function(tag) {
  return tag in this.tagsLogic && this.tagsLogic[tag]['applicable'];
};


/**
 * Returns whether a tag is removable.
 */
TagsGallery.prototype.isTagRemovable = function(tag) {
  return tag in this.tagsLogic && this.tagsLogic[tag]['removable'];
};


/**
 * Builds html content with info about an item in the gallery.
 */
TagsGallery.prototype.getItemInfo = function(item, i) {
  return item;
};


/**
 * Builds html content with buttons for labeling relevancy an item in the gallery,
 * such as Yes, No, Maybe.
 */
TagsGallery.prototype.getItemButtons = function(item, i) {
  var w = 12;
  var a = this.isTagApplicable(item) ? 'clickable' : 'not-clickable';
  var r = this.isTagRemovable(item) ? 'clickable' : 'not-clickable';
  return '<img actionType="Remove" src="img/remove.png" width="' + w + 'px" class="' + r + '">'
    + '<img actionType="Apply" src="img/apply.png" width="' + w + 'px" class="' + a + '">';
};


/**
 * Handles click in an item.
 */
TagsGallery.prototype.onItemClick = function(item, i) {
  __sig__.emit(__sig__.tag_clicked, item);
};


/**
 * Handles item focus.
 */
TagsGallery.prototype.onItemFocus = function(item, i, onFocus) {
  __sig__.emit(__sig__.tag_focus, item, onFocus);
};


/**
 * Handles click in an item.
 */
TagsGallery.prototype.onItemActionClick = function(item, i, actionType) {
  this.applyOrRemoveTag(item, actionType);
};


/**
 * Applies or removes tag.
 */
TagsGallery.prototype.applyOrRemoveTag = function(tag, actionType, opt_pages) {
  // Handles tags logic.
  if (tag in this.tagsLogic) {
    var logicForTag = this.tagsLogic[tag];

    if (actionType == 'Apply') {
      // Removes tags in negate.
      for (var i in logicForTag.negate) {
        var negateTag = logicForTag.negate[i];
        __sig__.emit(__sig__.tag_action_clicked, negateTag, 'Remove', opt_pages);
      }
      if (logicForTag.applicable && !logicForTag.isVirtual) {
        __sig__.emit(__sig__.tag_action_clicked, tag, actionType, opt_pages);
      }
    } else {
      // Removes tag when removable.
      if (logicForTag.removable) {
        __sig__.emit(__sig__.tag_action_clicked, tag, actionType, opt_pages);
      }
    }
  } else {
    __sig__.emit(__sig__.tag_action_clicked, tag, actionType, opt_pages);
  }
};



/**
 * Returns applicable tags.
 */
TagsGallery.prototype.getApplicableTags = function() {
  var gallery = this;
  return this.items.filter(function(tag) {
    return gallery.isTagApplicable(tag);
  });
};
